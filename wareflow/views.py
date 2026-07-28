# from django.shortcuts import render

# Create your views here.
# def login_page(request):
#     return render(request, 'login.html')
# def dashboard(request):
#     return render(request, 'dashboard.html')
# def products(request):
#     return render(request, 'products.html')
# def stock_in(request):
#     return render(request, 'stock_in.html')
# def stock_out(request):
#     return render(request, 'stock_out.html')
# def alerts(request):
#     return render(request, 'alerts.html')
# def reports(request):
#     return render(request, 'reports.html')

from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Banner
from .forms import ProductForm
from django.db.models import F, Sum, Count, FloatField, ExpressionWrapper
from django.db.models.functions import TruncDate
from .models import Sale
import datetime
import json
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
import csv
import io
from django.urls import reverse

def dashboard(request):
    total_products = Product.objects.count()
    stock_in_count = Product.objects.filter(quantity__gt=0).count()
    low_stock = Product.objects.filter(quantity__lte=F('minimum_stock'), quantity__gt=0).count()
    stock_out = Product.objects.filter(quantity=0).count()
    available_stock = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0
    low_stock_products = Product.objects.filter(quantity__lte=F('minimum_stock'))

    stock_predictions = []
    products_for_prediction = Product.objects.order_by('quantity')[:8]
    for p in products_for_prediction:
        if p.quantity <= 0:
            status = 'Out of Stock'
            prediction = 'Restock immediately to avoid lost sales.'
        elif p.quantity <= p.minimum_stock:
            status = 'Critical'
            prediction = 'Stock is at or below the minimum threshold.'
        elif p.quantity <= p.minimum_stock * 2:
            status = 'Warning'
            prediction = 'Stock will run low soon; monitor and reorder.'
        else:
            status = 'Healthy'
            prediction = 'Stock level is healthy for current demand.'

        stock_predictions.append({
            'name': p.name,
            'category': p.category,
            'quantity': p.quantity,
            'minimum_stock': p.minimum_stock,
            'status': status,
            'prediction': prediction,
        })

    # Prefer Banner images for the carousel; if none, fall back to Product images
    carousel_items = []
    banners = Banner.objects.all()
    if banners.exists():
        for b in banners:
            if b.image:
                carousel_items.append({'url': b.image.url, 'title': b.title or ''})
    else:
        products_with_images = Product.objects.filter(image__isnull=False).exclude(image='')[:5]
        for p in products_with_images:
            if p.image:
                carousel_items.append({'url': p.image.url, 'title': p.name})

    context = {
        'total_products': total_products,
        'stock_in': stock_in_count,
        'low_stock': low_stock,
        'stock_out': stock_out,
        'available_stock': available_stock,
        'carousel_items': carousel_items,
        'low_stock_products': low_stock_products,
        'stock_predictions': stock_predictions,
    }

    return render(request, 'dashboard.html', context)

def product_list(request):
    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        products = Product.objects.filter(Q(name__icontains=q) | Q(category__icontains=q))
    else:
        products = Product.objects.all()

    low_stock_products = Product.objects.filter(quantity__lte=F('minimum_stock'))
    return render(request, 'product_list.html',
                  {'products': products, 'low_stock_products': low_stock_products, 'q': q})

def add_product(request):
    form = ProductForm(request.POST or None, request.FILES or None)

    if form.is_valid():
        form.save()
        return redirect('product_list')

    low_stock_products = Product.objects.filter(quantity__lte=F('minimum_stock'))
    return render(request,
                  'product_form.html',
                  {'form': form, 'title': 'Add Product', 'low_stock_products': low_stock_products})

def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product
    )

    if form.is_valid():
        form.save()
        return redirect('product_list')

    low_stock_products = Product.objects.filter(quantity__lte=F('minimum_stock'))
    return render(request,
                  'product_form.html',
                  {'form': form, 'title': 'Edit Product', 'product': product, 'low_stock_products': low_stock_products})

def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.delete()
        return redirect('product_list')

    low_stock_products = Product.objects.filter(quantity__lte=F('minimum_stock'))
    return render(request,
                  'delete.html',
                  {'product': product, 'low_stock_products': low_stock_products})

def stock_in(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        qty = int(request.POST['quantity'])
        product.quantity += qty
        product.save()
        return redirect('product_list')

    low_stock_products = Product.objects.filter(quantity__lte=F('minimum_stock'))
    return render(request,
                  'stock_in.html',
                  {'product': product, 'low_stock_products': low_stock_products})

def stock_out(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        qty = int(request.POST['quantity'])

        if product.quantity >= qty:
            product.quantity -= qty
            product.save()
            # record sale
            try:
                Sale.objects.create(product=product, quantity=qty, total_price=round(product.price * qty, 2))
            except Exception:
                pass

        return redirect('product_list')

    low_stock_products = Product.objects.filter(quantity__lte=F('minimum_stock'))
    return render(request,
                  'stock_out.html',
                  {'product': product, 'low_stock_products': low_stock_products})

def alerts(request):
    products = Product.objects.filter(quantity__lte=F('minimum_stock'))

    return render(request,
                  'alerts.html',
                  {'products': products})


def reports(request):
    # date filter
    start = request.GET.get('start')
    end = request.GET.get('end')

    qs = Sale.objects.all()
    if start:
        qs = qs.filter(date__date__gte=start)
    if end:
        qs = qs.filter(date__date__lte=end)

    total_revenue = qs.aggregate(total=Sum('total_price'))['total'] or 0
    total_items = qs.aggregate(items=Sum('quantity'))['items'] or 0

    # daily totals
    daily = qs.annotate(day=TruncDate('date')).values('day').annotate(total=Sum('total_price')).order_by('day')
    labels = [d['day'].isoformat() for d in daily]
    data = [round(d['total'], 2) for d in daily]

    context = {
        'total_revenue': total_revenue,
        'total_items': total_items,
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data),
        'start': start,
        'end': end,
        'low_stock_products': Product.objects.filter(quantity__lte=F('minimum_stock')),
    }

    return render(request, 'reports.html', context)


def chat(request):
    # simple chat UI
    return render(request, 'chat.html', {'low_stock_products': Product.objects.filter(quantity__lte=F('minimum_stock'))})


def chat_api(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')

    data = request.POST or request.body
    # support form-encoded or raw JSON
    message = ''
    if request.POST.get('message'):
        message = request.POST.get('message')
    else:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            message = payload.get('message', '')
        except Exception:
            message = ''

    if not message:
        return JsonResponse({'reply': 'Please ask a question about inventory.'})

    msg = message.lower()

    # 1) low stock
    if 'low stock' in msg or 'low in stock' in msg or 'which products are low' in msg:
        qs = Product.objects.filter(quantity__lte=F('minimum_stock'))
        if not qs.exists():
            return JsonResponse({'reply': 'No products are currently low in stock.'})
        items = [f"{p.name} ({p.quantity})" for p in qs[:20]]
        reply = 'Low stock items: ' + ', '.join(items)
        return JsonResponse({'reply': reply})
        

    # 2) category count, e.g., how many laptops
    import re
    m = re.search(r'how many ([a-zA-Z0-9\- ]+)', msg)
    if m:
        term = m.group(1).strip()
        # try to sum by category or name
        total = Product.objects.filter(category__icontains=term).aggregate(total=Sum('quantity'))['total']
        if not total:
            total = Product.objects.filter(name__icontains=term).aggregate(total=Sum('quantity'))['total']
        total = total or 0
        reply = f'There are {int(total)} units of "{term}" available.'
        return JsonResponse({'reply': reply})

    # 3) today's stock-out items
    if 'today' in msg and ('stock out' in msg or 'stock-out' in msg or 'stockout' in msg or 'stock out items' in msg):
        today = datetime.date.today()
        sales_today = Sale.objects.filter(date__date=today)
        if not sales_today.exists():
            return JsonResponse({'reply': "No stock-out transactions recorded today."})
        items = []
        for s in sales_today.select_related('product')[:50]:
            items.append(f"{s.product.name} x{s.quantity}")
        reply = 'Today\'s stock-out transactions: ' + ', '.join(items)
        return JsonResponse({'reply': reply})
    if 'all products' in msg or 'show products' in msg or 'list products' in msg:
        products = Product.objects.all()[:50]
        if not products.exists():
            return JsonResponse({'reply': "No products found."})
        items = [f"{p.name} ({p.quantity})" for p in products]
        reply = 'Products: ' + ', '.join(items)
        return JsonResponse({'reply': reply})
        
    # General Ventra project questions
    if 'ventra' in msg or 'what is ventra' in msg or 'what is this' in msg:
        reply = (
            "Ventra is the Smart Inventory Management application in this project. "
            "Key features: manage products, record stock in/out, view low-stock alerts, and generate sales reports. "
            "Use the Products page to add/edit/delete items, Stock In/Stock Out to adjust quantities, Alerts to see low stock, and Reports for sales data."
        )
        return JsonResponse({'reply': reply})

    if 'how to add product' in msg or 'add product' in msg or 'create product' in msg:
        reply = (
            "To add a product: go to the Products page and click 'Add'. Fill in the product form (name, category, price, quantity, minimum stock, image) and submit. "
            "You can also upload an image for the product."
        )
        return JsonResponse({'reply': reply})

    if 'restock' in msg or 'stock in' in msg or 'how to restock' in msg:
        reply = (
            "To restock a product: open the product from the Products list and use the 'Stock In' action to add quantity. "
            "Alternatively, use the Stock In form on the product details."
        )
        return JsonResponse({'reply': reply})

    if 'sell' in msg or 'stock out' in msg or 'how to sell' in msg or 'record sale' in msg:
        reply = (
            "To record a sale use the Stock Out action for a product and enter the quantity sold. "
            "The app will decrement product quantity and record a Sale entry for reporting."
        )
        return JsonResponse({'reply': reply})

    if 'reports' in msg or 'sales report' in msg or 'where is reports' in msg:
        reply = (
            "Reports are under the Reports page. You can filter by date range to see daily revenue and items sold. "
            "Use the chart to review sales trends."
        )
        return JsonResponse({'reply': reply})

    if 'alerts' in msg or 'low stock' in msg or 'where is alerts' in msg:
        reply = (
            "Alerts show products that are at or below their minimum stock level. Open Alerts from the navigation or check the low-stock badge on Products."
        )
        return JsonResponse({'reply': reply})

    # Navigation helpers
    if 'where is' in msg or 'open' in msg or 'go to' in msg or 'how do i get to' in msg:
        if 'products' in msg:
            try:
                url = reverse('product_list')
            except Exception:
                url = '/products/'
            return JsonResponse({'reply': f'Products page: {url}'})
        if 'reports' in msg:
            try:
                url = reverse('reports')
            except Exception:
                url = '/reports/'
            return JsonResponse({'reply': f'Reports page: {url}'} )
        if 'alerts' in msg:
            try:
                url = reverse('alerts')
            except Exception:
                url = '/alerts/'
            return JsonResponse({'reply': f'Alerts page: {url}'} )
        if 'chat' in msg:
            try:
                url = reverse('chat')
            except Exception:
                url = '/chat/'
            return JsonResponse({'reply': f'Chat page: {url}'} )
        if 'dashboard' in msg:
            try:
                url = reverse('dashboard')
            except Exception:
                url = '/'
            return JsonResponse({'reply': f'Dashboard: {url}'} )

    # Product detail / info queries: "show product <name>", "tell me about <name>"
    m = re.search(r"(?:show|details|tell me about|what is|info about) (?:product )?([a-zA-Z0-9\- ]+)", msg)
    if m:
        name = m.group(1).strip()
        # normalize common trailing words like 'stock' or 'available'
        name = re.sub(r"\b(stock|in stock|available|units)\b", "", name).strip()
        if name and name not in ('ventra', 'this'):
            qs = Product.objects.filter(name__icontains=name)[:5]
            if not qs.exists():
                # try searching by category
                qs = Product.objects.filter(category__icontains=name)[:5]
                if not qs.exists():
                    return JsonResponse({'reply': f'No product found matching "{name}".'})
            p = qs[0]
            reply = (f'{p.name}: category {p.category or "(none)"}, price {getattr(p, "price", "N/A")}, '
                     f'quantity {p.quantity}, minimum stock {p.minimum_stock}.')
            return JsonResponse({'reply': reply})

    # Support queries like "what is laptop stock" or "what's iphone in stock"
    m2 = re.search(r"(?:what(?:'s| is)|show|how many) (?:the )?([a-zA-Z0-9\- ]+?) (?:stock|in stock|available|units)?\??$", msg)
    if m2:
        name = m2.group(1).strip()
        name = re.sub(r"\b(stock|in stock|available|units)\b", "", name).strip()
        if name and name not in ('ventra', 'this'):
            total = Product.objects.filter(name__icontains=name).aggregate(total=Sum('quantity'))['total']
            if not total:
                total = Product.objects.filter(category__icontains=name).aggregate(total=Sum('quantity'))['total']
            total = total or 0
            return JsonResponse({'reply': f'There are {int(total)} units of "{name}" available.'})

    # Reorder suggestions
    if 'reorder' in msg or 'what to reorder' in msg or 'reorder suggestions' in msg or 'need to reorder' in msg:
        # consider items at or below minimum_stock * 1.5 as candidates
        candidates = Product.objects.filter(quantity__lte=F('minimum_stock') * 1.5).order_by('quantity')[:20]
        if not candidates.exists():
            return JsonResponse({'reply': 'No products currently need reordering.'})
        suggestions = []
        for p in candidates:
            target = max(p.minimum_stock * 2, p.minimum_stock + 5)
            suggested = max(int(target - p.quantity), 1)
            suggestions.append(f"{p.name}: order {suggested} units (current {p.quantity}, min {p.minimum_stock})")
        try:
            url = reverse('export_products_csv') + '?low=1'
        except Exception:
            url = '/export/products/csv/?low=1'
        reply = 'Reorder suggestions:\n' + '; '.join(suggestions[:10]) + f".\nYou can export these to CSV: {url}"
        return JsonResponse({'reply': reply})

    # Export commands
    if 'export' in msg or 'download csv' in msg or 'download products' in msg or 'csv' in msg:
        low = 'low' in msg or 'alerts' in msg or 'low stock' in msg
        try:
            url = reverse('export_products_csv')
        except Exception:
            url = '/export/products/csv/'
        if low:
            url = url + '?low=1'
            return JsonResponse({'reply': f'Export low-stock products CSV: {url}'})
        return JsonResponse({'reply': f'Export products CSV: {url}'})

    # Supplier info - not present in current models
    if 'supplier' in msg or 'supplier info' in msg or 'who supplies' in msg:
        reply = (
            "Supplier data is not available in the current Ventra schema. "
            "To add it, create a Supplier model and link it to Product (ForeignKey), then run migrations. "
            "Example: add fields `supplier_name`, `contact`, `phone`, and `email` to track suppliers."
        )
        return JsonResponse({'reply': reply})

    # fallback
    return JsonResponse({'reply': "I can help with: 'Which products are low in stock?', 'How many <category> are available?', or 'Show me today's stock-out items.'"})

    

def mini_chart_data(request):
    """Return JSON labels and data for the last 7 days of total sales."""
    today = datetime.date.today()
    start = today - datetime.timedelta(days=6)

    qs = Sale.objects.filter(date__date__gte=start)
    daily = qs.annotate(day=TruncDate('date')).values('day').annotate(total=Sum('total_price')).order_by('day')

    # build a dict for quick lookup
    data_map = {d['day'].isoformat(): float(d['total'] or 0) for d in daily}

    labels = []
    data = []
    for i in range(7):
        day = (start + datetime.timedelta(days=i))
        key = day.isoformat()
        labels.append(key)
        data.append(round(data_map.get(key, 0), 2))

    return JsonResponse({'labels': labels, 'data': data})


def export_products_csv(request):
    """Export products as CSV. Use ?low=1 to export only low-stock products."""
    low = request.GET.get('low')
    if low:
        qs = Product.objects.filter(quantity__lte=F('minimum_stock'))
    else:
        qs = Product.objects.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'name', 'category', 'price', 'quantity', 'minimum_stock'])
    for p in qs:
        writer.writerow([p.id, p.name, p.category, getattr(p, 'price', ''), p.quantity, p.minimum_stock])

    resp = HttpResponse(output.getvalue(), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="products.csv"'
    return resp


