"""Rutas HTTP mínimas de la fase 0."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.models import Product, User, UserRole
from app.models import OrderKind
from app.csrf import attach, issue, verify
from app.requests_service import InvalidRequest, create_request
from app.identity import new_session, current_user
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    products = db.scalars(select(Product).options(selectinload(Product.creator)).order_by(Product.id)).all()
    return templates.TemplateResponse(request=request, name="home.html", context={"app_name": get_settings().app_name, "products": products})


@router.get("/catalogo", response_class=HTMLResponse)
def catalog(request: Request, db: Session = Depends(get_db)):
    products = db.scalars(select(Product).options(selectinload(Product.creator)).order_by(Product.id)).all()
    return templates.TemplateResponse(request=request, name="catalog.html", context={"app_name": get_settings().app_name, "products": products})


@router.get("/productos/{slug}", response_class=HTMLResponse)
def product_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).options(selectinload(Product.creator)).where(Product.slug == slug))
    if product is None:
        return templates.TemplateResponse(request=request, name="404.html", status_code=404, context={"app_name": get_settings().app_name, "message": "No encontramos ese producto en la demo."})
    token = issue()
    response = templates.TemplateResponse(request=request, name="product.html", context={"app_name": get_settings().app_name, "product": product, "csrf_token": token})
    attach(response, token)
    return response


@router.post("/productos/{slug}/consulta", response_class=HTMLResponse)
def product_request(slug: str, request: Request, alias: str = Form(""), message: str = Form(""), offer: str = Form(""), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    product = db.scalar(select(Product).options(selectinload(Product.creator)).where(Product.slug == slug))
    if product is None:
        return templates.TemplateResponse(request=request, name="404.html", status_code=404, context={"app_name": get_settings().app_name, "message": "No encontramos ese producto en la demo."})
    try:
        order, recovery = create_request(db, alias=alias, message=message, offer=offer, kind=OrderKind.PRODUCT_INQUIRY, product=product, visitor=current_user(db, request.cookies.get("ta_session")))
    except InvalidRequest as exc:
        token = issue()
        response = templates.TemplateResponse(request=request, name="product.html", status_code=422, context={"app_name": get_settings().app_name, "product": product, "error": str(exc), "alias_value": alias[:80], "message_value": message[:2000], "offer_value": offer[:30], "csrf_token": token})
        attach(response, token)
        return response
    response = RedirectResponse("/solicitud-recibida", status_code=303)
    if current_user(db, request.cookies.get("ta_session")) is None:
        response.set_cookie("ta_session", new_session(db, order.requester), httponly=True, samesite="lax", secure=get_settings().app_env == "production", max_age=43200)
    response.set_cookie("ta_new_recovery", recovery, httponly=True, samesite="strict", secure=get_settings().app_env == "production", max_age=300)
    return response


@router.get("/figura-personalizada", response_class=HTMLResponse)
def custom_form(request: Request, db: Session = Depends(get_db)):
    token = issue()
    response = templates.TemplateResponse(request=request, name="custom_form.html", context={"app_name": get_settings().app_name, "csrf_token": token})
    attach(response, token)
    return response


@router.post("/figura-personalizada", response_class=HTMLResponse)
async def custom_request(request: Request, db: Session = Depends(get_db)):
    if request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise HTTPException(status_code=415, detail="Las fotografías no se reciben en esta aplicación.")
    form = await request.form()
    alias = str(form.get("alias", ""))
    description = str(form.get("description", ""))
    verify(request, str(form.get("csrf_token", "")))
    try:
        order, recovery = create_request(db, alias=alias, message=description, kind=OrderKind.CUSTOM_FIGURE, visitor=current_user(db, request.cookies.get("ta_session")))
    except InvalidRequest as exc:
        token = issue()
        response = templates.TemplateResponse(request=request, name="custom_form.html", status_code=422, context={"app_name": get_settings().app_name, "error": str(exc), "alias_value": alias[:80], "description_value": description[:2000], "csrf_token": token})
        attach(response, token)
        return response
    response = RedirectResponse("/solicitud-recibida", status_code=303)
    if current_user(db, request.cookies.get("ta_session")) is None:
        response.set_cookie("ta_session", new_session(db, order.requester), httponly=True, samesite="lax", secure=get_settings().app_env == "production", max_age=43200)
    response.set_cookie("ta_new_recovery", recovery, httponly=True, samesite="strict", secure=get_settings().app_env == "production", max_age=300)
    return response


@router.get("/solicitud-recibida", response_class=HTMLResponse)
def confirmation(request: Request, db: Session = Depends(get_db)):
    recovery = request.cookies.get("ta_new_recovery")
    response = templates.TemplateResponse(request=request, name="confirmation.html", context={"app_name": get_settings().app_name, "recovery": recovery})
    response.delete_cookie("ta_new_recovery")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/creadores", response_class=HTMLResponse)
def creators(request: Request, db: Session = Depends(get_db)):
    people = db.scalars(select(User).where(User.role == UserRole.STUDENT).options(selectinload(User.products)).order_by(User.alias)).all()
    return templates.TemplateResponse(request=request, name="creators.html", context={"app_name": get_settings().app_name, "creators": people})


@router.get("/health", response_model=dict[str, str])
def health():
    return {"status": "ok"}

