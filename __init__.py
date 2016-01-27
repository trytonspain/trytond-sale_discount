#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from .sale import *
from .move import *
from .price_list import *


def register():
    Pool.register(
        Sale,
        SaleLine,
        Move,
        PriceList,
        PriceListLine,
        module='sale_discount', type_='model')
    Pool.register(
        SaleReport,
        module='sale_discount', type_='report')
