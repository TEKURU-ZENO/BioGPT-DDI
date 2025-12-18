BioGPT-DDI

Biomedical GPT for Drug–Drug Interaction Prediction and Explainable Reports

BioGPT-DDI is a biomedical AI project that uses the BioGPT language model to predict drug–drug interactions (DDIs) and generate explainable clinical summaries.
The project demonstrates how large language models can be applied to healthcare and biomedical text analysis through a simple web-based interface.

Project Overview

Drug–drug interactions are a major cause of adverse drug reactions and medical complications. Existing systems often rely on static databases that cannot easily adapt to new information.

BioGPT-DDI addresses this problem by:

Using a biomedical language model (BioGPT) trained on scientific literature

Predicting interactions between two drugs

Generating clear, human-readable explanations for the predicted interaction

This project is designed as a prototype system for learning and experimentation in biomedical NLP.

Key Features

Predicts whether two drugs interact

Indicates interaction severity

Generates explainable clinical text using BioGPT

Simple web interface for user input and result display

Lightweight backend API for inference

Project Structure

api/
Contains backend logic for handling requests, running the BioGPT model, and returning predictions and explanations.

src/
Frontend source code for the user interface, including pages and UI components.

public/
Static assets such as images or icons.

package.json
Project dependencies and scripts.

vercel.json
Deployment configuration for hosting the application.

Technologies Used

Language Model: BioGPT

Frontend: JavaScript (React-based)

Backend: Node.js API

Deployment: Vercel

How the System Works

The user enters two drug names in the web interface.

The frontend sends the drug pair to the backend API.

The backend processes the input using the BioGPT model.

The model predicts a possible interaction and generates an explanation.

The result is returned and displayed on the user interface.

Example

Input:

Drug 1: Aspirin

Drug 2: Warfarin

Output:

Interaction: Severe

Explanation:
Aspirin may increase the anticoagulant effect of Warfarin, leading to a higher risk of bleeding.

Use Cases

Academic and major projects in AI and healthcare

Biomedical NLP experimentation

Understanding applications of LLMs in clinical decision support

Prototyping healthcare AI systems

Future Enhancements

Support for more drug datasets

Improved explanation clarity and formatting

Interaction confidence scoring

Multi-drug interaction analysis

UI/UX improvements

License

This project is licensed under the MIT License.

Acknowledgements

BioGPT by Microsoft Research

Biomedical datasets such as DrugBank and TWOSIDES

Open-source NLP and AI research community
