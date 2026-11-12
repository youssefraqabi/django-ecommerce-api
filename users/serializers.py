from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )
    
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )
    
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "password2",
        ]
        read_only_fields = ["id"]
        
    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({
                "password": "Passwords do not match."
            })
            
        validate_password(attrs["password"])
        
        email = attrs["email"].strip().lower()
        
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({
                "email": "This email is already registered."
            })
            
        attrs["email"] = email
        return attrs
    
    def create(self, validated_data):
        validated_data.pop("password2")
        
        user = User.objects.create_user(
            **validated_data
        )
        
        return user
    
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "date_joined",
        ]
        read_only_fields = fields