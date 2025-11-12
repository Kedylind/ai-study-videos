from django.http import JsonResponse, HttpResponse


def health(request):
    return JsonResponse({"status": "ok"})


def home(request):
    return HttpResponse("<h1>Hidden Hill staging is live</h1>")
