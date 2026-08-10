from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, normalize_email, verify_password
from app.db.models import Event, Product, Recommendation, RecommendationItem, User, UserBehaviorState, UserRole


def create_user(db: Session, email: str, password: str, role: UserRole = UserRole.USER) -> User:
    user = User(email=normalize_email(email), password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == normalize_email(email))
    return db.scalar(statement)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_product(db: Session, **product_data: object) -> Product:
    product = Product(**product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_product_by_id(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def list_products(db: Session, active_only: bool = False) -> list[Product]:
    statement = select(Product)
    if active_only:
        statement = statement.where(Product.active.is_(True))
    statement = statement.order_by(Product.id.asc())
    return list(db.scalars(statement).all())


def create_event(db: Session, **event_data: object) -> Event:
    event = Event(**event_data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_user_behavior_state(db: Session, user_id: int, **state_data: object) -> UserBehaviorState:
    state = db.get(UserBehaviorState, user_id)
    if state is None:
        state = UserBehaviorState(user_id=user_id, **state_data)
        db.add(state)
    else:
        for key, value in state_data.items():
            setattr(state, key, value)
    db.commit()
    db.refresh(state)
    return state


def create_recommendation(db: Session, **recommendation_data: object) -> Recommendation:
    recommendation = Recommendation(**recommendation_data)
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return recommendation


def create_recommendation_item(db: Session, **item_data: object) -> RecommendationItem:
    item = RecommendationItem(**item_data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item