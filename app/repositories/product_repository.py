from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_external_product_id(self, external_product_id: str) -> Product | None:
        stmt = select(Product).where(Product.external_product_id == external_product_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_or_create(
        self,
        external_product_id: str | None,
        *,
        fallback_name: str | None = None,
    ) -> Product | None:
        if not external_product_id:
            return None

        product = self.get_by_external_product_id(external_product_id)
        if product:
            return product

        product = Product(
            external_product_id=external_product_id,
            name=fallback_name or external_product_id,
        )
        self.db.add(product)
        self.db.flush()
        return product
