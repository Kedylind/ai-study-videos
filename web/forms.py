from django import forms


class PaperUploadForm(forms.Form):
    """Simple form to upload a paper (PMID or PMCID)."""

    paper_id = forms.CharField(
        required=True,
        label="PubMed ID or PMCID",
        help_text="Enter a PMID (e.g. 33963468) or PMCID (e.g. PMC10979640)",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
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
