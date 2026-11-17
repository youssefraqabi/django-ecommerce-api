from django.contrib import admin
from .models import Cart, CartItem
# Register your models here.

class CartItemInLine(admin.TabularInline):
    model = CartItem
    extra = 0
    
    
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "created_at"]
    search_fields = ["user__username"]
    inlines = [CartItemInLine]

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ["id", "cart", "product", "quantity"]