import re
import spacy
import pdfplumber
from PIL import Image
from docx import Document
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from .models import Contract, ExtractedData
from .forms import ContractReviewForm
import pytesseract
from datetime import datetime, timedelta

# Load spaCy model globally
nlp = spacy.load("en_core_web_sm")

# Define keywords for contextual extraction
DATE_KEYWORDS = [
    "start date", "effective date", "commences on", "valid from", "begins on",
    "end date", "termination date", "expires on", "valid until", "ends on"
]
RENEWAL_KEYWORDS = [
    "auto-renewal", "renewal terms", "valid until", "termination notice",
    "validity period", "Initial Term", "extension", "renewable for",
    "subscription period", "renewal clause"
]
PAYMENT_KEYWORDS = ["payment", "fee", "cost", "price"]

# Landing page
def landing_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'contracts/landing_page.html')

# Upload contract
@login_required
def upload_contract(request):
    if request.method == "POST":
        file = request.FILES.get('contract')
        contract = Contract.objects.create(user=request.user, file=file)
        extract_data_from_contract(contract)
        return redirect('review_contract', pk=contract.pk)
    return render(request, 'contracts/upload.html')

# Review contract
@login_required
def review_contract(request, pk):
    contract = get_object_or_404(Contract, pk=pk, user=request.user)
    extracted_data = ExtractedData.objects.filter(contract=contract).first()

    if request.method == "POST":
        form = ContractReviewForm(request.POST, instance=extracted_data)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ContractReviewForm(instance=extracted_data)

    print("Form Initial Data:", form.initial)  # Debug log
    return render(request, 'contracts/review_contract.html', {
        'form': form,
        'contract': contract
    })

# Dashboard
@login_required
def dashboard(request):
    contracts = Contract.objects.filter(user=request.user).order_by('-upload_date')
    return render(request, 'contracts/dashboard.html', {'contracts': contracts})

# Contract details
@login_required
def contract_details(request, pk):
    contract = get_object_or_404(Contract, pk=pk, user=request.user)
    extracted_data = ExtractedData.objects.filter(contract=contract).first()
    return render(request, 'contracts/contract_details.html', {
        'contract': contract,
        'extracted_data': extracted_data,
    })

# Extract data from contract
def extract_data_from_contract(contract):
    file_path = contract.file.path
    extracted_data = {
        "party_names": [],
        "start_date": None,
        "end_date": None,
        "renewal_terms": None,
        "payment_details": None,
    }

    # Extract text based on file type
    if file_path.endswith('.pdf'):
        full_text = extract_text_from_pdf(file_path)
    elif file_path.endswith(('.jpg', '.png')):
        full_text = extract_text_from_image(file_path)
    elif file_path.endswith('.docx'):
        full_text = extract_text_from_docx(file_path)
    else:
        full_text = ""

    doc = nlp(full_text)
    extracted_data["party_names"] = clean_party_names(extract_party_names(doc))
    extracted_data["start_date"], extracted_data["end_date"] = extract_dates_with_context(full_text)
    extracted_data["renewal_terms"] = extract_renewal_terms(full_text, extracted_data)
    if not extracted_data["end_date"]:
        extracted_data["end_date"] = infer_end_date_from_terms(extracted_data["start_date"], extracted_data["renewal_terms"])
    extracted_data["payment_details"] = extract_payment_details(full_text)

    print("Extracted Data:", extracted_data)  # Debug log

    # Save extracted data
    ExtractedData.objects.create(
        contract=contract,
        party_names=", ".join(extracted_data["party_names"]),
        start_date=extracted_data["start_date"],
        end_date=extracted_data["end_date"],
        renewal_terms=extracted_data["renewal_terms"],
        payment_details=extracted_data["payment_details"],
    )

# Extract text functions
def extract_text_from_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        return " ".join(page.extract_text() for page in pdf.pages if page.extract_text())

def extract_text_from_image(file_path):
    return pytesseract.image_to_string(Image.open(file_path))

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())

# Entity extraction functions
def extract_party_names(doc):
    return [ent.text for ent in doc.ents if ent.label_ in {"ORG", "PERSON"}]

def clean_party_names(party_names):
    """
    Remove irrelevant entries and duplicates, normalizing party names.
    """
    exclude_keywords = {"notify", "signature", "signatures", "service provider", "address", "ownership"}
    cleaned_names = [
        name.strip() for name in party_names
        if not any(keyword in name.lower() for keyword in exclude_keywords)
    ]
    # Remove duplicates while preserving case sensitivity
    return list({name.lower(): name for name in cleaned_names}.values())


# Date extraction
def parse_date(date_string):
    formats = ["%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d", "%B %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_string.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def extract_dates_with_context(text):
    """
    Extract start and end dates from text using contextual matching and fallback.
    """
    start_date_keywords = ["start date", "effective date", "commences on", "valid from", "begins on"]
    end_date_keywords = ["end date", "termination date", "expires on", "valid until", "ends on"]

    start_date, end_date = None, None

    # Extract start date
    for keyword in start_date_keywords:
        matches = re.findall(
            rf"{keyword}[:\s]*(\b\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|\b\w+ \d{{1,2}}, \d{{4}})",
            text,
            re.IGNORECASE,
        )
        if matches:
            start_date = parse_date(matches[0])
            print(f"Start Date Matched: {matches[0]}")
            break

    # Extract end date
    for keyword in end_date_keywords:
        matches = re.findall(
            rf"{keyword}[:\s]*(\b\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|\b\w+ \d{{1,2}}, \d{{4}})",
            text,
            re.IGNORECASE,
        )
        if matches:
            end_date = parse_date(matches[0])
            print(f"End Date Matched: {matches[0]}")
            break

    # Fallback: Use the first two dates
    dates = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\b\w+ \d{1,2}, \d{4}\b", text)
    if not start_date and dates:
        start_date = parse_date(dates[0])
    if not end_date and len(dates) > 1:
        end_date = parse_date(dates[1])

    # Ensure `end_date` is after `start_date`
    if start_date and end_date and start_date >= end_date:
        end_date = None

    return start_date, end_date


def infer_end_date_from_terms(start_date, renewal_terms):
    """
    Infer the end date from the start date and renewal terms that specify a duration.
    """
    if not start_date or not renewal_terms:
        return None

    duration_match = re.search(r"(\d+)\s*(month|year)s?", renewal_terms, re.IGNORECASE)
    if duration_match:
        duration = int(duration_match.group(1))
        unit = duration_match.group(2).lower()
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        if unit == "month":
            end_date_obj = start_date_obj + timedelta(days=30 * duration)
        elif unit == "year":
            end_date_obj = start_date_obj + timedelta(days=365 * duration)
        return end_date_obj.strftime("%Y-%m-%d")
    return None

def extract_renewal_terms(text, extracted_data):
    """
    Extract renewal terms using extended keyword matching and multiline patterns.
    """
    for keyword in RENEWAL_KEYWORDS:
        match = re.search(rf"{keyword}[:\s]*(.*?)(\.|\n|$)", text, re.IGNORECASE)
        if match:
            renewal_terms = normalize_text(match.group(1))
            print(f"Renewal Terms Matched: {renewal_terms}")
            return renewal_terms
    return "No renewal terms found."

def extract_payment_details(text):
    """
    Extract and format payment details from the text.
    """
    payments = re.findall(r"\$\d+[.,]?\d*|\€\d+[.,]?\d*", text)
    if payments:
        return ", ".join(payments)
    return "No payment details found."

# Text normalization
def normalize_text(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"’", "'", text)
    text = re.sub(r"-+", "-", text)
    text = re.sub(r"[^\w\s.,$%&@#-]", "", text)
    return text.strip()

# Signup
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('upload_contract')
    else:
        form = UserCreationForm()
    return render(request, 'auth/signup.html', {'form': form})

# Delete contract
@login_required
def delete_contract(request, pk):
    contract = get_object_or_404(Contract, pk=pk, user=request.user)
    contract.delete()
    return redirect('dashboard')
