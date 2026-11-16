# AI governance note for insurance AI systems

Owner: Head of Data Science, Example Ltd · Version: 1.0 · Review date: 2026-09-30

This note records how our responsible AI approach applies to each AI system we use in insurance.

## Proportionality

Controls scale with customer impact: a claims triage model gets full review, an internal search tool gets a light check.

## Risk management

Each AI system has an entry in the risk register with a named owner, a rating and a treatment plan reviewed every quarter.

## Fairness

Pricing and claims models are tested for outcome gaps between customer groups. A gap above 5 percent opens a review.

## Data governance

Training data comes from the Example Ltd policy and claims systems. Quality and representativeness checks run before each retrain.

## Records

Training runs, test results and model versions are kept in the model registry for ten years.

## Transparency

Customers are told when an AI system supports a decision and can ask for a human explanation of the outcome.

## Human oversight

A claims handler can override or stop any model output. Declines always get a human review.

## Robustness and security

Accuracy and drift are monitored weekly. Models are tested against adversarial inputs before release.
