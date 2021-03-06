# -*- coding: utf-8 -*-
from openerp import osv, models, fields, api, _
from openerp.osv import fields as old_fields
from openerp.exceptions import except_orm, Warning
from openerp.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class AccountInvoiceTax(models.Model):
    _inherit = "account.invoice.tax"

    def _compute_base_amount(self):
        for tax in self:
            if tax.tax_id.price_include:
                base = 0.0
                for line in tax.invoice_id.tax_id.invoice_line_ids:
                    if tax.tax_id in line.tax_id:
                        base += (line.price_tax_included / (
                            1 + tax.tax_id.amount / 100))
                        # valor sin redondeo
                        base += sum((line.tax_id.filtered(
                            lambda t: t.include_base_amount) - tax.tax_id).mapped(
                                'amount'))
                tax.base = tax.invoice_id.currency_id.round(base)
                # se redondea global
            else:
                super(AccountInvoiceTax,tax)._compute_base_amount()

class account_invoice(models.Model):
    _inherit = "account.invoice"

    def _compute_amount(self):
        for inv in self:
            currency = inv.currency_id or None
            amount_total = 0
            for line in inv.invoice_line_ids:
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                taxes = line.tax_id.with_context({'round':False}).compute_all(price, currency, line.quantity, product=line.product_id, partner=inv.partner_id)
                if taxes and taxes['total_included'] > 0:
                    amount_total += taxes['total_included']
                else:
                    amount_total += line.price_tax_included

            inv.amount_tax = sum(line.amount for line in inv.tax_line_ids)
            inv.amount_untaxed = currency.round(amount_total - inv.amount_tax)
            inv.amount_total = inv.amount_untaxed + inv.amount_tax
            amount_total_company_signed = inv.amount_total
            amount_untaxed_signed = inv.amount_untaxed
            if inv.currency_id and inv.currency_id != inv.company_id.currency_id:
                amount_total_company_signed = inv.currency_id.compute(inv.amount_total, inv.company_id.currency_id)
                amount_untaxed_signed = inv.currency_id.compute(inv.amount_untaxed, inv.company_id.currency_id)
            sign = inv.type in ['in_refund', 'out_refund'] and -1 or 1
            inv.amount_total_company_signed = amount_total_company_signed * sign
            inv.amount_total_signed = inv.amount_total * sign
            inv.amount_untaxed_signed = amount_untaxed_signed * sign


    def get_document_class_default(self, document_classes):
        if self.turn_issuer.vat_affected not in ['SI']:
            exempt_ids = [
                self.env.ref('l10n_cl_invoice.dc_y_f_dtn').id,
                self.env.ref('l10n_cl_invoice.dc_y_f_dte').id]
            for document_class in document_classes:
                if document_class.sii_document_class_id.id in exempt_ids:
                    document_class_id = document_class.id
                    break
                else:
                    document_class_id = document_classes.ids[0]
        else:
            document_class_id = document_classes.ids[0]
        return document_class_id

    # determina el giro issuer por default
    @api.multi
    @api.depends('partner_id')
    def _get_available_issuer_turns(self):
        for rec in self:
            available_turn_ids = rec.company_id.company_activities_ids
            for turn in available_turn_ids:
                rec.turn_issuer = turn.id



    def _printed_prices(self, cr, uid, ids, name, args, context=None):
        res = {}

        for invoice in self.browse(cr, uid, ids, context=context):
            printed_amount_untaxed = invoice.amount_untaxed
            printed_tax_id = [x.id for x in invoice.tax_line]

            vat_amount = sum([
                x.tax_amount for x in invoice.tax_line if\
                x.tax_code_id.parent_id.name == 'IVA'])

            other_taxes_amount = sum(
                line.other_taxes_amount for line in invoice.invoice_line)
            exempt_amount = sum(
                line.exempt_amount for line in invoice.invoice_line)
            vat_tax_ids = [
                x.id for x in invoice.tax_line if\
                x.tax_code_id.parent_id.name == 'IVA']

            if not invoice.vat_discriminated:
                printed_amount_untaxed = sum(
                    line.printed_price_subtotal for line in\
                    invoice.invoice_line)
                printed_tax_ids = [
                    x.id for x in invoice.tax_line if\
                    x.tax_code_id.parent_id.name != 'IVA']
            res[invoice.id] = {
                'printed_amount_untaxed': printed_amount_untaxed,
                'printed_tax_ids': printed_tax_ids,
                'printed_amount_tax': invoice.amount_total - printed_amount_untaxed,
                'vat_tax_ids': vat_tax_ids,
                'vat_amount': vat_amount,
                'other_taxes_amount': other_taxes_amount,
                'exempt_amount': exempt_amount,
            }
        return res

    _columns = {
        'printed_amount_tax': old_fields.function(
            _printed_prices, type='float',
            digits_compute=dp.get_precision('Account'),
            string='Tax', multi='printed',),
        'printed_amount_untaxed': old_fields.function(
            _printed_prices,
            type='float', digits_compute=dp.get_precision('Account'),
            string='Subtotal', multi='printed',),
        'printed_tax_ids': old_fields.function(
            _printed_prices,
            type='one2many', relation='account.invoice.tax', string='Tax',
            multi='printed'),
        'exempt_amount': old_fields.function(
            _printed_prices, type='float',
            digits_compute=dp.get_precision('Account'),
            string='Exempt Amount', multi='printed'),
        'vat_tax_ids': old_fields.function(
            _printed_prices,
            type='one2many', relation='account.invoice.tax',
            string='VAT Taxes', multi='printed'),
        'vat_amount': old_fields.function(
            _printed_prices, type='float',
            digits_compute=dp.get_precision('Account'),
            string='Vat Amount', multi='printed'),
        'other_taxes_amount': old_fields.function(
            _printed_prices, type='float',
            digits_compute=dp.get_precision('Account'),
            string='Other Taxes Amount', multi='printed')
    }

    turn_issuer = fields.Many2one(
        'partner.activities',
        'Giro Emisor', readonly=True, store=True, required=False,
        states={'draft': [('readonly', False)]},
        compute=_get_available_issuer_turns)

    @api.multi
    def name_get(self):
        TYPES = {
            'out_invoice': _('Invoice'),
            'in_invoice': _('Supplier Invoice'),
            'out_refund': _('Refund'),
            'in_refund': _('Supplier Refund')}
        result = []
        for inv in self:
            result.append(
                (inv.id, "%s %s" % (inv.document_number or TYPES[inv.type], inv.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(
                [('document_number', '=', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

    @api.one
    @api.depends('journal_id', 'partner_id', 'turn_issuer')
    def _get_available_journal_document_class(self):
        invoice_type = self.type
        document_class_ids = []
        document_class_id = False

        # Lo hicimos asi porque si no podria dar errores si en el context habia
        # un default de otra clase
        self.available_journal_document_class_ids = self.env[
            'account.journal.sii_document_class']
        if invoice_type in [
                'out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            operation_type = self.get_operation_type(invoice_type)

            if self.use_documents:
                letter_ids = self.get_valid_document_letters(
                    self.partner_id.id, operation_type, self.company_id.id)

                domain = [
                    ('journal_id', '=', self.journal_id.id),
                    '|', ('sii_document_class_id.document_letter_id',
                          'in', letter_ids),
                         ('sii_document_class_id.document_letter_id',
                          '=', False)]

                # If document_type in context we try to serch specific document
                document_type = self._context.get('document_type', False)
                if document_type:
                    document_classes = self.env[
                        'account.journal.sii_document_class'].search(
                        domain + [('sii_document_class_id.document_type',
                                   '=', document_type)])
                    if document_classes.ids:
                        # revisar si hay condicion de exento, para poner como
                        # primera alternativa estos
                        document_class_id = self.get_document_class_default(
                            document_classes)

                # For domain, we search all documents
                document_classes = self.env[
                    'account.journal.sii_document_class'].search(domain)
                document_class_ids = document_classes.ids

                # If not specific document type found, we choose another one
                if not document_class_id and document_class_ids:
                    # revisar si hay condicion de exento, para poner
                    # como primera alternativa estos
                    # todo: manejar más fino el documento por defecto.
                    document_class_id = self.get_document_class_default(
                        document_classes)
        self.available_journal_document_class_ids = document_class_ids
        self.journal_document_class_id = document_class_id


    @api.one
    @api.depends('sii_document_class_id', 'sii_document_number', 'number')
    def _get_document_number(self):
        if self.sii_document_number and self.sii_document_class_id:
            document_number = (
                self.sii_document_class_id.doc_code_prefix or '') + self.sii_document_number
        else:
            document_number = self.number
        self.document_number = document_number


    @api.one
    @api.depends(
        'sii_document_class_id',
        'sii_document_class_id.document_letter_id',
        'sii_document_class_id.document_letter_id.vat_discriminated',
        'company_id',
        'company_id.invoice_vat_discrimination_default',)
    def get_vat_discriminated(self):
        vat_discriminated = False
        # agregarle una condicion: si el giro es afecto a iva, debe
        # seleccionar factura, de lo contrario boleta (to-do)
        if self.sii_document_class_id.document_letter_id.vat_discriminated \
                or self.company_id.invoice_vat_discrimination_default \
                        == 'discriminate_default':
            vat_discriminated = True
        self.vat_discriminated = vat_discriminated

    vat_discriminated = fields.Boolean(
        'Discriminate VAT?',
        compute="get_vat_discriminated",
        store=True,
        readonly=False,
        help="Discriminate VAT on Quotations and Sale Orders?")

    available_journal_document_class_ids = fields.Many2many(
        'account.journal.sii_document_class',
        compute='_get_available_journal_document_class',
        string='Available Journal Document Classes')
    supplier_invoice_number = fields.Char(
        copy=False)
    journal_document_class_id = fields.Many2one(
        'account.journal.sii_document_class',
        'Documents Type',
        compute="_get_available_journal_document_class",
        readonly=True,
        store=True,
        states={'draft': [('readonly', False)]})
    sii_document_class_id = fields.Many2one(
        'sii.document_class',
        related='journal_document_class_id.sii_document_class_id',
        string='Document Type',
        copy=False,
        readonly=True,
        store=True)
    sii_document_number = fields.Char(
        string='Document Number',
        copy=False,
        readonly=True,)
    responsability_id = fields.Many2one(
        'sii.responsability',
        string='Responsability',
        related='commercial_partner_id.responsability_id',
        store=True,
        )
    formated_vat = fields.Char(
        string='Responsability',
        related='commercial_partner_id.formated_vat',)
    iva_uso_comun = fields.Boolean(string="Uso Común", readonly=True, states={'draft': [('readonly', False)]}) # solamente para compras tratamiento del iva
    no_rec_code = fields.Selection([
                    ('1', 'Compras destinadas a IVA a generar operaciones no gravados o exentas.'),
                    ('2', 'Facturas de proveedores registrados fuera de plazo.'),
                    ('3', 'Gastos rechazados.'),
                    ('4', 'Entregas gratuitas (premios, bonificaciones, etc.) recibidos.'),
                    ('9', 'Otros.')],
                    string="Código No recuperable",
                    readonly=True, states={'draft': [('readonly', False)]})# @TODO select 1 automático si es emisor 2Categoría

    document_number = fields.Char(
        compute='_get_document_number',
        string='Document Number',
        readonly=True,
    )
    next_invoice_number = fields.Integer(
        related='journal_document_class_id.sequence_id.number_next_actual',
        string='Next Document Number',
        readonly=True)
    use_documents = fields.Boolean(
        related='journal_id.use_documents',
        string='Use Documents?',
        readonly=True)

    @api.one
    @api.constrains('supplier_invoice_number', 'partner_id', 'company_id')
    def _check_reference(self):
        if self.type in ['out_invoice', 'out_refund'] and self.reference and\
                        self.state == 'open':
            domain = [('type', 'in', ('out_invoice', 'out_refund')),
                      # ('reference', '=', self.reference),
                      ('document_number', '=', self.document_number),
                      ('journal_document_class_id.sii_document_class_id', '=',
                       self.journal_document_class_id.sii_document_class_id.id),
                      ('company_id', '=', self.company_id.id),
                      ('id', '!=', self.id)]
            invoice_ids = self.search(domain)
            if invoice_ids:
                raise Warning(
                    _('Supplier Invoice Number must be unique per Supplier and \
Company!'))

    _sql_constraints = [
        ('number_supplier_invoice_number',
            'unique(supplier_invoice_number, partner_id, company_id)',
         'Supplier Invoice Number must be unique per Supplier and Company!'),
    ]

    @api.multi
    def action_number(self):
        obj_sequence = self.env['ir.sequence']

        # We write document_number field with next invoice number by
        # document type
        for obj_inv in self:
            invtype = obj_inv.type
            # if we have a journal_document_class_id is beacuse we are in a
            # company that use this function
            # also if it has a reference number we use it (for example when
            # cancelling for modification)
            if obj_inv.journal_document_class_id and not \
                    obj_inv.sii_document_number:
                if invtype in ('out_invoice', 'out_refund'):
                    if not obj_inv.journal_document_class_id.sequence_id:
                        raise osv.except_osv(_('Error!'), _(
                            'Please define sequence on the journal related\
documents to this invoice.'))
                    sii_document_number = obj_sequence.next_by_id(
                        obj_inv.journal_document_class_id.sequence_id.id)
                elif invtype in ('in_invoice', 'in_refund'):
                    sii_document_number = obj_inv.supplier_invoice_number
                obj_inv.write({'sii_document_number': sii_document_number})
                document_class_id = obj_inv.journal_document_class_id.sii_document_class_id.id
                obj_inv.move_id.write(
                    {'document_class_id': document_class_id,
                     'sii_document_number': self.sii_document_number})
        res = super(account_invoice, self).action_number()

        return res

    def get_operation_type(self, cr, uid, invoice_type, context=None):
        if invoice_type in ['in_invoice', 'in_refund']:
            operation_type = 'purchase'
        elif invoice_type in ['out_invoice', 'out_refund']:
            operation_type = 'sale'
        else:
            operation_type = False
        return operation_type

    def get_valid_document_letters(
            self, cr, uid, partner_id, operation_type='sale',
            company_id=False, context=None):
        if context is None:
            context = {}

        document_letter_obj = self.pool.get('sii.document_letter')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        partner = self.pool.get('res.partner').browse(
            cr, uid, partner_id, context=context)

        if not partner_id or not company_id or not operation_type:
            return []

        partner = partner.commercial_partner_id

        if not company_id:
            company_id = context.get('company_id', user.company_id.id)
        company = self.pool.get('res.company').browse(
            cr, uid, company_id, context)

        if operation_type == 'sale':
            issuer_responsability_id = company.partner_id.responsability_id.id
            receptor_responsability_id = partner.responsability_id.id
        elif operation_type == 'purchase':
            issuer_responsability_id = partner.responsability_id.id
            receptor_responsability_id = company.partner_id.responsability_id.id
        else:
            raise except_orm(_('Operation Type Error'),
                             _('Operation Type Must be "Sale" or "Purchase"'))

        if not company.partner_id.responsability_id.id:
            raise except_orm(_('You have not settled a tax payer type for your\
             company.'),
             _('Please, set your company tax payer type (in company or \
             partner before to continue.'))

        document_letter_ids = document_letter_obj.search(cr, uid, [(
            'issuer_ids', 'in', issuer_responsability_id),
            ('receptor_ids', 'in', receptor_responsability_id)],
            context=context)
        return document_letter_ids
