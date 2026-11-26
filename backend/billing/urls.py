from django.urls import path

from billing import views

urlpatterns = [
    path("billing/plans", views.BillingPlansView.as_view(), name="billing-plans"),
    path("billing/orders", views.CreateOrderView.as_view(), name="billing-order"),
    path("billing/verify", views.VerifyPaymentView.as_view(), name="billing-verify"),
    path("billing/invoices", views.RealInvoiceListView.as_view(), name="billing-invoices"),
]
