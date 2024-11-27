import re
import spacy
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import pdfplumber
from PIL import Image
from docx import Document
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from .models import Contract, ExtractedData
import pytesseract
from datetime import datetime

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
    elif file_path.endswith('.docx'):
        full_text = extract_text_from_docx(file_path)
    else:
        full_text = ""

    # Use spaCy to extract entities
    doc = nlp(full_text)
    extracted_data["party_names"] = extract_party_names(doc)

    # Extract dates with improved logic
    extracted_data["start_date"], extracted_data["end_date"] = extract_dates_with_context(full_text)

    # Extract renewal terms with extended keyword list
    extracted_data["renewal_terms"] = extract_renewal_terms(full_text, extracted_data)

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


def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])


def extract_party_names(doc):
    # Extract organization and person names, filter irrelevant matches
    party_names = [ent.text for ent in doc.ents if ent.label_ in ["ORG", "PERSON"]]
    # Deduplicate and remove generic terms
    filtered_names = list(set([name.strip() for name in party_names if len(name) > 3 and not name.lower() in ["subscriber", "service provider"]]))
    return filtered_names



def extract_dates_with_context(text):
    # Improved date extraction with context
    dates = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\b\w+ \d{1,2}, \d{4}\b", text)
    start_date, end_date = None, None

    for keyword in DATE_KEYWORDS:
        keyword_contexts = re.findall(rf"{keyword}[:\s]*(\b\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|\b\w+ \d{{1,2}}, \d{{4}})", text, re.IGNORECASE)
        for context in keyword_contexts:
            parsed_date = parse_date(context)  # Convert to YYYY-MM-DD
            if parsed_date:
                if "start" in keyword.lower() or "arrival" in keyword.lower() or "begins on" in keyword.lower():
                    start_date = start_date or parsed_date
                elif "end" in keyword.lower() or "termination" in keyword.lower():
                    end_date = end_date or parsed_date

    # Fallback to extracting the first two dates if no context found
    if not start_date and dates:
        start_date = parse_date(dates[0])  # Convert to YYYY-MM-DD
    if not end_date and len(dates) > 1:
        end_date = parse_date(dates[1])  # Convert to YYYY-MM-DD

    return start_date, end_date


def parse_date(date_string):
    """
    Convert a date string to the YYYY-MM-DD format. Returns None if parsing fails.
    """
    formats = ["%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
def extract_renewal_terms(text, extracted_data):
    # Extend keyword list and search for terms
    keywords = ["auto-renewal", "renewal terms", "valid until", "termination notice", "validity period", "Initial Term"]
    for keyword in keywords:
        match = re.search(rf"{keyword}.*", text, re.IGNORECASE)
        if match:
            renewal_terms = match.group(0)
            # Extract dates from renewal terms if present
            dates_in_terms = re.findall(r"\b\w+ \d{1,2}, \d{4}\b", renewal_terms)
            if len(dates_in_terms) >= 1:
                extracted_data["start_date"] = extracted_data["start_date"] or dates_in_terms[0]
            if len(dates_in_terms) >= 2:
                extracted_data["end_date"] = extracted_data["end_date"] or dates_in_terms[1]
            return renewal_terms
    return None




def extract_payment_details(text):
    payments = re.findall(r"\$\d+[.,]?\d*|\€\d+[.,]?\d*", text)
    return ", ".join(payments) if payments else None

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
