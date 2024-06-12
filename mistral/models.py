from django.db import models
from django.contrib.auth.models import User

class Owner(models.Model):
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=50)
    address = models.TextField()
    bio = models.TextField()
    tag = models.CharField(max_length=50)
    role = models.CharField(max_length=20, default='owner')  # Add role attribute

    def __str__(self):
        return self.full_name

class Member(models.Model):
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=50)
    address = models.TextField()
    bio = models.TextField()
    tag = models.CharField(max_length=50)
    role = models.CharField(max_length=20, default='member')  # Add role attribute

    def __str__(self):
        return self.full_name
