from django import forms


class PaperUploadForm(forms.Form):
    """Simple form to upload a paper (PMID or PMCID) or a PDF/text file."""

    paper_id = forms.CharField(
        required=False,
        label="PubMed ID or PMCID",
        help_text="Enter a PMID (e.g. 33963468) or PMCID (e.g. PMC10979640)",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    file = forms.FileField(
        required=False,
        label="Upload file",
        help_text="Optional: upload a PDF or text file instead of using PubMed",
    )

    access_code = forms.CharField(
        required=True,
        label="Access Code",
        help_text="Enter the access code to generate videos",
        widget=forms.PasswordInput(attrs={
            "placeholder": "Enter access code",
            "autocomplete": "one-time-code",  # Designed for codes, prevents password manager autofill
            "data-form-type": "other",
            "data-lpignore": "true",  # LastPass ignore
            "data-1p-ignore": "true",  # 1Password ignore
            "data-bwignore": "true",  # Bitwarden ignore
            "data-dashlane-ignore": "true",  # Dashlane ignore
            "readonly": "readonly",  # Will be removed by JavaScript on focus
            "onfocus": "this.removeAttribute('readonly')",
            "onclick": "this.removeAttribute('readonly')",
            "onkeydown": "this.removeAttribute('readonly')",
        }),
    )

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            # Check file extension
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError("Only PDF files are supported.")
            
            # Check file size (50MB max)
            max_size = 50 * 1024 * 1024  # 50MB in bytes
            if file.size > max_size:
                size_mb = file.size / (1024 * 1024)
                raise forms.ValidationError(
                    f"File size ({size_mb:.1f}MB) exceeds maximum allowed size (50MB)."
                )
        
        return file

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("paper_id") and not cleaned.get("file"):
            raise forms.ValidationError("Provide either a PubMed ID/PMCID or upload a file.")
        return cleaned
