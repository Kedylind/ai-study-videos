from django import forms


class PaperUploadForm(forms.Form):
    """Simple form to upload a paper (PMID or PMCID) or a PDF/text file."""

    paper_id = forms.CharField(
        required=False,
        label="PubMed ID or PMCID",
        help_text="Enter a PMID (e.g. 33963468) or PMCID (e.g. PMC10979640)",
    )

    file = forms.FileField(
        required=False,
        label="Upload file",
        help_text="Optional: upload a PDF or text file instead of using PubMed",
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("paper_id") and not cleaned.get("file"):
            raise forms.ValidationError("Provide either a PubMed ID/PMCID or upload a file.")
        return cleaned
