# from django.urls import path
# from . import views

# urlpatterns = [
#     path('', views.login_page, name='wareflow'),
#     path('dashboard/', views.dashboard, name='dashboard'),
#     path('products/', views.products, name='products'),
#     paath('stock_in/', views.stock_in, name='stock_in'),
#     path('stock_out/', views.stock_out, name='stock_out'),
#     path('reports/', views.reports, name='reports'),
# ]
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('products/',
         views.product_list,
         name='product_list'),

    path('add/',
         views.add_product,
         name='add_product'),

    path('edit/<int:pk>/',
         views.edit_product,
         name='edit_product'),

    path('delete/<int:pk>/',
         views.delete_product,
         name='delete_product'),

    path('stock-in/<int:pk>/',
         views.stock_in,
         name='stock_in'),

    path('stock-out/<int:pk>/',
         views.stock_out,
         name='stock_out'),

    path('alerts/',
         views.alerts,
         name='alerts'),
    path('chat/',
         views.chat,
         name='chat'),
    path('chat/api/',
         views.chat_api,
         name='chat_api'),
     path('export/products/csv/', views.export_products_csv, name='export_products_csv'),
    path('api/mini-chart/',
         views.mini_chart_data,
         name='mini_chart_data'),
    path('reports/',
         views.reports,
         name='reports'),
]