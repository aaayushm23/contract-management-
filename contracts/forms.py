from django import forms
from .models import ExtractedData

class ContractReviewForm(forms.ModelForm):
    class Meta:
        model = ExtractedData
        fields = ['party_names', 'start_date', 'end_date', 'renewal_terms', 'payment_details']
