from transformers import pipeline, set_seed

try:
    generator = pipeline('text-generation', model="microsoft/biogpt")
except Exception as e:
    print(f"Error loading BioGPT generator model: {e}")
    generator = None

def generate_report(prompt: str) -> str:
    """Generates a text report based on a given prompt using BioGPT."""
    if not generator:
        return "Error: Report generation model could not be loaded."

    set_seed(42)
    try:
        generated_sequences = generator(prompt, max_length=150, num_return_sequences=1, do_sample=True, temperature=0.7)
        full_text = generated_sequences['generated_text']
        report = full_text.replace(prompt, "").strip()
        return report if report else "A summary could not be generated for this interaction."
    except Exception as e:
        return f"Error during report generation: {str(e)}"