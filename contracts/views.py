import re
import spacy
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import pdfplumber
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from .models import Contract, ExtractedData
import pytesseract

# Load spaCy model globally
nlp = spacy.load("en_core_web_sm")

# Define possible keywords for date extraction
DATE_KEYWORDS = ["start date", "end date", "arrival date", "effective date", "termination date"]

@login_required
def upload_contract(request):
    if request.method == "POST":
        file = request.FILES.get('contract')
        contract = Contract.objects.create(user=request.user, file=file)
        extract_data_from_contract(contract)
        return redirect('dashboard')
    return render(request, 'contracts/upload.html')


def extract_data_from_contract(contract):
    file_path = contract.file.path
    extracted_data = {
        "party_names": [],
        "start_date": None,
        "end_date": None,
        "renewal_terms": None,
        "payment_details": None,
    }

    # Read the content of the file
    if file_path.endswith('.pdf'):
        full_text = extract_text_from_pdf(file_path)
    elif file_path.endswith(('.jpg', '.png')):
        full_text = extract_text_from_image(file_path)
    else:
        full_text = ""

    # Use spaCy to extract entities
    doc = nlp(full_text)
    extracted_data["party_names"] = extract_party_names(doc)

    # Extract dates with improved logic
    extracted_data["start_date"], extracted_data["end_date"] = extract_dates_with_context(full_text)

    # Extract renewal terms with extended keyword list
    extracted_data["renewal_terms"] = extract_renewal_terms(full_text)

    # Extract payment details with improved filtering
    extracted_data["payment_details"] = extract_payment_details(full_text)

    # Save extracted data to the database
    ExtractedData.objects.create(
        contract=contract,
        party_names=", ".join(extracted_data["party_names"]),
        start_date=extracted_data["start_date"],
        end_date=extracted_data["end_date"],
        renewal_terms=extracted_data["renewal_terms"],
        payment_details=extracted_data["payment_details"],
    )



def extract_text_from_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        return "".join(page.extract_text() for page in pdf.pages if page.extract_text())


def extract_text_from_image(file_path):
    return pytesseract.image_to_string(Image.open(file_path))


def extract_party_names(doc):
    # Extract organization and person names, filter irrelevant matches
    party_names = [ent.text for ent in doc.ents if ent.label_ in ["ORG", "PERSON"]]
    # Filter out short or meaningless matches
    return [name for name in party_names if len(name) > 3 and not name.isdigit()]

def extract_dates_with_context(text):
    # Improved date extraction with context
    dates = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", text)
    start_date, end_date = None, None

    for keyword in DATE_KEYWORDS:
        keyword_contexts = re.findall(rf"{keyword}[:\s]*\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}", text, re.IGNORECASE)
        for context in keyword_contexts:
            date = re.search(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", context).group()
            if "start" in keyword.lower() or "arrival" in keyword.lower():
                start_date = start_date or date
            elif "end" in keyword.lower() or "termination" in keyword.lower():
                end_date = end_date or date

    # Fall back to extracting the first two dates if no context found
    if not start_date and dates:
        start_date = dates[0]
    if not end_date and len(dates) > 1:
        end_date = dates[1]

    return start_date, end_date

def extract_renewal_terms(text):
    # Extend keyword list and search for terms
    keywords = ["auto-renewal", "renewal terms", "valid until", "termination notice", "validity period"]
    for keyword in keywords:
        match = re.search(rf"{keyword}.*", text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None



def extract_payment_details(text):
    # Improved logic for payment details
    payments = re.findall(r"\d+[.,]?\d*\s*%|\$\d+[.,]?\d*|\€\d+[.,]?\d*", text)
    filtered_payments = []
    for payment in payments:
        # Check for relevance (e.g., percentage near "interest rate")
        if re.search(r"(interest|rate|payment|fee)", text, re.IGNORECASE):
            filtered_payments.append(payment)
    return ", ".join(filtered_payments) if filtered_payments else None

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log in the user after signup
            return redirect('upload_contract')  # Redirect to the upload page
    else:
        form = UserCreationForm()
    return render(request, 'auth/signup.html', {'form': form})


@login_required
def dashboard(request):
    contracts = Contract.objects.filter(user=request.user).order_by('-upload_date')
    return render(request, 'contracts/dashboard.html', {'contracts': contracts})


@login_required
def contract_details(request, pk):
    contract = get_object_or_404(Contract, pk=pk, user=request.user)
    extracted_data = ExtractedData.objects.filter(contract=contract).first()
    return render(request, 'contracts/contract_details.html', {
        'contract': contract,
        'extracted_data': extracted_data,
    })
