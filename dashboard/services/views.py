# Aggiungi in cima agli import:
from .services.ml_labels import save_malattia_label, get_all_labels
from .services.ml_predict import predict_rischio, predict_tutti
from .services.ml_train import train_and_save, model_exists

# Sostituisci dashboard_home con:
def dashboard_home(request):
    misure   = get_latest_measurements()
    rischi   = predict_tutti()
    rischi_map = {r["node_id"]: r for r in rischi}
    context  = {"titolo": "Vineguard – Dashboard vigneto",
                 "misure": misure, "rischi_map": rischi_map,
                 "model_ready": model_exists()}
    return render(request, "dashboard/index.html", context)

# Aggiungi queste 4 nuove view:
def ml_risk_json(request):
    node_id = request.GET.get("node_id")
    window  = int(request.GET.get("window", 7))
    data = predict_rischio(node_id, window) if node_id else predict_tutti(window)
    return JsonResponse({"ml_risk": data})

@csrf_exempt
def ml_label_json(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    payload  = json.loads(request.body.decode("utf-8"))
    node_id  = payload.get("node_id")
    if not node_id:
        return JsonResponse({"error": "node_id obbligatorio"}, status=400)
    window_days = int(payload.get("window_days", 7))
    save_malattia_label(node_id, window_days=window_days)
    return JsonResponse({"status": "label_saved", "node_id": node_id}, status=201)

def ml_labels_list(request):
    return JsonResponse({"labels": get_all_labels()})

@csrf_exempt
def ml_train_json(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    return JsonResponse(train_and_save())
