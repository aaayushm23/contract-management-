from django.db import models
from django.contrib.auth.models import User

class Contract(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='contracts/')
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Contract uploaded by {self.user.username} on {self.upload_date}"

class ExtractedData(models.Model):
    contract = models.OneToOneField(Contract, on_delete=models.CASCADE)
    party_names = models.TextField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    renewal_terms = models.TextField(null=True, blank=True)
    payment_details = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Extracted Data for Contract {self.contract.id}"

class Notification(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    notification_date = models.DateTimeField()
    sent = models.BooleanField(default=False)
