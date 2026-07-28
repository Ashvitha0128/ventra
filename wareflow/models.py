from django.db import models


# Create your models here.
class Product(models.Model):
    name=models.CharField(max_length=100)
    category=models.CharField(max_length=100)
    price=models.FloatField()
    quantity=models.IntegerField()
    image=models.ImageField(upload_to='products/' , blank=True, null=True)
    minimum_stock=models.IntegerField(default=5)

    def __str__(self):
        return self.name




class Banner(models.Model):
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='banners/')

    def __str__(self):
        return self.title


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    total_price = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sale: {self.product.name} x{self.quantity} @ {self.total_price}"
    



