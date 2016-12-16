# This file is part of sale_discount module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.sale.sale import SaleReport as OriginalSaleReport
from trytond.modules.account_invoice_discount import discount_digits
from trytond.modules.account_invoice_discount.invoice import DiscountMixin

__all__ = ['Sale', 'SaleLine', 'SaleReport', 'discount_digits']

STATES = {
    'invisible': Eval('type') != 'line',
    'required': Eval('type') == 'line',
    'readonly': Eval('sale_state') != 'draft',
    }


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'
    sale_discount = fields.Numeric('Sale Discount',
        digits=discount_digits, states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'],
        help='This discount will be applied in all lines after their own '
        'discount.')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        if not cls.lines.context:
            cls.lines.context = {}
        cls.lines.context['sale_discount'] = Eval('sale_discount')
        cls.lines.depends.append('sale_discount')

    @staticmethod
    def default_sale_discount():
        return Decimal(0)

    @fields.depends('sale_discount', 'lines', methods=['lines'])
    def on_change_sale_discount(self):
        for line in self.lines:
            line.apply_sale_discount(self.sale_discount)
        self.on_change_lines()


class SaleLine(DiscountMixin):
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.gross_unit_price.on_change_with.add('_parent_sale.sale_discount')
        cls.gross_unit_price.on_change_with.add('sale')
        cls.discount.on_change.add('sale')
        cls.discount.on_change.add('_parent_sale.sale_discount')
        cls.amount.on_change_with.add('_parent_sale.sale_discount')
        cls.amount.on_change_with.add('sale')

    @fields.depends('sale', '_parent_sale.sale_discount')
    def on_change_with_gross_unit_price(self, name=None):
        gross_unit_price = super(
            SaleLine, self).on_change_with_gross_unit_price(name)
        digits = self.__class__.gross_unit_price.digits[1]
        if Transaction().context.get('skip_sale_discount', False):
            return gross_unit_price
        if (gross_unit_price and self.sale and
                self.sale.sale_discount != Decimal(1)):
            sale_discount = self.sale.sale_discount or Decimal(0)
            gross_unit_price = gross_unit_price / (1 - sale_discount)
            gross_unit_price = gross_unit_price.quantize(
                Decimal(str(10.0 ** -digits)))
            return gross_unit_price
        return gross_unit_price

    def apply_sale_discount(self, sale_discount):
        if not self.unit_price:
            return
        with Transaction().set_context(skip_sale_discount=True):
            self.set_unit_price_from_gross_unit_price(
                self.gross_unit_price)
        unit_price = self.unit_price * (1 - sale_discount)
        digits = self.__class__.unit_price.digits[1]
        unit_price = unit_price.quantize(
            Decimal(str(10.0 ** -digits)))
        if unit_price != self.unit_price:
            self.unit_price = unit_price
        self.amount = self.on_change_with_amount()

    @fields.depends('discount', 'unit_price', '_parent_sale.sale_discount',
        'sale')
    def on_change_product(self):
        super(SaleLine, self).on_change_product()
        self.gross_unit_price = self.unit_price
        self.set_unit_price_from_gross_unit_price(self.gross_unit_price)

    @fields.depends('discount', 'unit_price', '_parent_sale.sale_discount',
        'sale')
    def on_change_quantity(self):
        super(SaleLine, self).on_change_quantity()
        self.gross_unit_price = self.unit_price
        self.set_unit_price_from_gross_unit_price(self.gross_unit_price)

    def get_invoice_line(self):
        lines = super(SaleLine, self).get_invoice_line()
        for line in lines:
            discount = Decimal(0)
            if self.discount and self.sale and self.sale.sale_discount:
                discount = (Decimal('1.0')
                    - (Decimal('1.0') - self.discount)
                    * (Decimal('1.0') - self.sale.sale_discount))
                pass
            elif self.sale and self.sale.sale_discount:
                discount = self.sale.sale_discount
            elif self.discount:
                discount = self.discount
            line.discount = discount
        return lines


class SaleReport(OriginalSaleReport):
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale.discount'
