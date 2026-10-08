---
license: apache-2.0
language:
  - en
library_name: transformers
pipeline_tag: text-classification
base_model: distilbert-base-uncased
datasets:
  - imdb
  - sst2
tags:
  - sentiment
  - text-classification
model-index:
  - name: demo-sentiment
    results:
      - task:
          type: text-classification
        dataset:
          type: imdb
          name: IMDB
        metrics:
          - type: accuracy
            value: 0.93
            name: Accuracy
          - type: f1
            value: 0.92
            name: F1
---

# demo-sentiment

A small sentiment classifier fine-tuned from DistilBERT.

## Limitations

English movie reviews only.
