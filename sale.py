# This file is part of sale_discount module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.sale.sale import SaleReport as OriginalSaleReport
from trytond.modules.product import price_digits
from trytond.modules.account_invoice_discount import discount_digits
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

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        sales_todo = []
        for sales, _ in zip(actions, actions):
            sales_todo.extend(sales)
        super(Sale, cls).write(*args)
        cls.apply_discount_to_lines(sales_todo)

    @classmethod
    def create(cls, vlist):
        sales = super(Sale, cls).create(vlist)
        cls.apply_discount_to_lines(sales)
        return sales

    @classmethod
    def apply_discount_to_lines(cls, sales):
        Line = Pool().get('sale.line')
        to_write = []
        for sale in sales:
            for line in sale.lines:
                old_unit_price = line.unit_price
                line.update_prices()
                if old_unit_price != line.unit_price:
                    to_write.append(line)
        if to_write:
            Line.save(to_write)


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    gross_unit_price = fields.Numeric('Gross Price', digits=price_digits,
        states=STATES, depends=['type', 'sale_state'])
    gross_unit_price_wo_round = fields.Numeric('Gross Price without rounding',
        digits=(16, price_digits[1] + discount_digits[1]), readonly=True)
    discount = fields.Numeric('Discount', digits=discount_digits,
        states=STATES, depends=['type', 'sale_state'])

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.unit_price.states['readonly'] = True
        cls.unit_price.digits = (20, price_digits[1] + discount_digits[1])
        if 'discount' not in cls.unit.on_change:
            cls.unit.on_change.add('discount')
        cls.unit.on_change.add('_parent_sale.sale_discount')
        if 'discount' not in cls.amount.on_change_with:
            cls.amount.on_change_with.add('discount')
        cls.amount.on_change_with.add('_parent_sale.sale_discount')
        if 'gross_unit_price' not in cls.amount.on_change_with:
            cls.amount.on_change_with.add('gross_unit_price')

    def update_prices(self):
        unit_price = None
        gross_unit_price = gross_unit_price_wo_round = self.gross_unit_price
        sale_discount = Transaction().context.get('sale_discount')

        if sale_discount == None:
            if self.sale and hasattr(self.sale, 'sale_discount'):
                sale_discount = self.sale.sale_discount or Decimal(0)
            else:
                sale_discount = Decimal(0)
        if self.gross_unit_price is not None and (self.discount is not None
                or sale_discount is not None):
            unit_price = self.gross_unit_price
            if self.discount:
                unit_price *= (1 - self.discount)
            if sale_discount:
                unit_price *= (1 - sale_discount)

            if self.discount and sale_discount:
                discount = (self.discount + sale_discount
                    - self.discount * sale_discount)
                if discount != 1:
                    gross_unit_price_wo_round = unit_price / (1 - discount)
            elif self.discount and self.discount != 1:
                gross_unit_price_wo_round = unit_price / (1 - self.discount)
            elif sale_discount and sale_discount != 1:
                gross_unit_price_wo_round = unit_price / (1 - sale_discount)

            digits = self.__class__.unit_price.digits[1]
            unit_price = unit_price.quantize(Decimal(str(10.0 ** -digits)))

            digits = self.__class__.gross_unit_price.digits[1]
            gross_unit_price = gross_unit_price_wo_round.quantize(
                Decimal(str(10.0 ** -digits)))

        self.gross_unit_price = gross_unit_price
        self.gross_unit_price_wo_round = gross_unit_price_wo_round
        self.unit_price = unit_price

    @fields.depends('gross_unit_price', 'discount',
        '_parent_sale.sale_discount')
    def on_change_gross_unit_price(self):
        return self.update_prices()

    @staticmethod
    def default_discount():
        return Decimal(0)

    @fields.depends('gross_unit_price', 'discount',
        '_parent_sale.sale_discount')
    def on_change_discount(self):
        return self.update_prices()

    @fields.depends('discount', 'unit_price', '_parent_sale.sale_discount')
    def on_change_product(self):
        super(SaleLine, self).on_change_product()
        self.gross_unit_price = self.unit_price
        self.discount = Decimal(0)

        if self.unit_price:
            self.gross_unit_price = self.unit_price
            self.update_prices()

    @fields.depends('discount', 'unit_price', '_parent_sale.sale_discount')
    def on_change_quantity(self):
        super(SaleLine, self).on_change_quantity()
        self.gross_unit_price = self.unit_price
        if not self.discount:
            self.discount = Decimal(0)

        if self.unit_price:
            self.gross_unit_price = self.unit_price
            self.update_prices()

    def get_invoice_line(self):
        lines = super(SaleLine, self).get_invoice_line()
        for line in lines:
            line.gross_unit_price = self.gross_unit_price
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

    @classmethod
    def create(cls, vlist):
        Sale = Pool().get('sale.sale')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('type', 'line') != 'line':
                continue
            if vals.get('unit_price') is None:
                vals['gross_unit_price'] = Decimal(0)
                continue

            if 'gross_unit_price' not in vals:
                gross_unit_price = vals['unit_price']
                if vals.get('discount') not in (None, 1):
                    gross_unit_price = (gross_unit_price
                        / (1 - vals['discount']))
                if vals.get('sale'):
                    sale = Sale(vals['sale'])
                    sale_discount = sale.sale_discount
                    if sale_discount not in (None, 1):
                        gross_unit_price = (gross_unit_price
                            / (1 - sale_discount))
                if gross_unit_price != vals['unit_price']:
                    digits = cls.gross_unit_price.digits[1]
                    gross_unit_price = gross_unit_price.quantize(
                        Decimal(str(10.0 ** -digits)))
                vals['gross_unit_price'] = gross_unit_price
            if not vals.get('discount'):
                vals['discount'] = Decimal(0)
        return super(SaleLine, cls).create(vlist)


class SaleReport(OriginalSaleReport):
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale.discount'
