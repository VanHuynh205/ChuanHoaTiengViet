# NVIDIA hosted Kimi K3: public terms investigation

Investigated: 2026-09-06. Scope: public documents only; no account, API inference, credentials or implementation changes. This establishes product constraints, not account-specific legal clearance.

## Evidence

The current [Kimi K3 modelcard](https://build.nvidia.com/moonshotai/kimi-k3/modelcard) explicitly links the API Trial Terms for the hosted service, the Open Model Agreement for the model, and Moonshot's license. Its commercial-use description concerns the model; it does not itself grant production access to the free hosted endpoint. No Kimi-specific retention exception or permission for personal data was visible in the public card.

[API Trial Terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf), sections 1–4:

- §§1.2/1.4 restrict service and generated-content use to internal testing/evaluation; production needs a separate subscription.
- §§2.6/4.3 exclude confidential, sensitive and personal data unless expressly permitted. Public availability does not establish permission or remove personal data.
- §2.3 states end-session non-storage/use, subject to exceptions. §2.4 covers specified services (30-day input/90-day fine-tuning output) and security/abuse logging; these periods are not a general Kimi retention schedule.
- §3.3 expressly includes input/output collection to improve products, including AI models, plus security logging and service-provider sharing. Therefore neither no-training nor zero-retention is established.
- §§2.2/3.5 involve affiliates/service providers and possible registration/usage sharing with third-party suppliers; they do not prove Moonshot receives Kimi prompts.

The [NIM FAQ](https://forums.developer.nvidia.com/t/nvidia-nim-faq/300317), displayed as September 2024 and still accessible, distinguishes prototyping from activities serving real users. It also mixes downloadable NIM licensing with hosted endpoints. Use its trial explanation as corroboration, not as a blanket claim that every Kimi deployment requires AI Enterprise. It supplies no guaranteed Kimi quota; limits depend on model/account/load.

The [Open Model Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-agreement/) permits commercial use of covered works. The linked [Moonshot license](https://huggingface.co/moonshotai/Kimi-K3/blob/main/LICENSE) is actually titled Kimi K3 License, despite the card's Modified MIT label. It contains conditions for large Model-as-a-Service businesses and large commercial products, with exceptions. Neither document overrides hosted-trial permission merely by allowing model use. Self-hosted weights, self-hosted NIM, and NVIDIA's hosted trial are distinct licensing questions.

## Product consequences (inferences)

1. Define the initial AI phase as genuine internal evaluation, with test data and evaluation outputs. A small logged-in user count alone is insufficient to establish that scope.
2. Do not yet promise ongoing free AI service for real customer work. If that is required, first establish a qualifying production arrangement; provider selection alone cannot settle it.
3. Keep dataset-only and advance disclosure. Restrict trial inputs to material the submitter may send, excluding personal/confidential content. Consent in this app cannot override provider restrictions.
4. Treat output-derived dictionary candidates as evaluation material until permissible downstream use is established; admin approval addresses correctness, not provider usage rights.

## Remaining unknowns

- Actual account subscription/accepted terms and any endpoint-specific disclosure or exception.
- Whether intended participants are internal evaluators or external users doing real work.
- Exact logging/retention periods and improvement processing for this endpoint; public terms do not resolve the tension between §§2.3 and 3.3 into a precise lifecycle.
- Named subprocessors, processing locations, and whether Moonshot receives content for this hosted deployment.
- Any applicable account production permission and conditions for using generated dictionary entries after evaluation.

The public-document investigation is complete. These unknowns require account evidence or provider clarification, not more repository inspection. No provider was contacted.
