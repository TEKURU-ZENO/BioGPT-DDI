from transformers import pipeline, AutoTokenizer

# --- CRITICAL STEP ---
# Replace 'YOUR_HF_USERNAME/biogpt-di-classifier-focal' with the model ID from Phase 1.
MODEL_ID = "tekuru/biogpt-ddi-focal" 

try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    classifier = pipeline(
        "text-classification",
        model=MODEL_ID,
        tokenizer=tokenizer
    )
except Exception as e:
    print(f"Error loading fine-tuned DDI classifier model: {e}")
    classifier = None

def predict_interaction(drug1: str, drug2: str) -> str:
    """Predicts the DDI type using the fine-tuned BioBERT model."""
    if not classifier:
        return "ERROR: DDI Prediction model not loaded."
    
    # Format the input with entity markers, exactly as done during training
    text = f"Interaction between <e1>{drug1}</e1> and <e2>{drug2}</e2>."
    
    try:
        result = classifier(text)
        return result['label']
    except Exception as e:
        print(f"Error during prediction: {e}")
        return "ERROR: Prediction failed."