--- 
title: Miscellaneous experiments in LLM finetuning
url_name: "misc-llm-experiments" 
tags: ["LLMs", "AI"] 
date: "2025-09-13" 

---

This project was initially a collaboration with [a friend](https://ivyzhang.me/) where my part would involve finetuning an LLM with some desired persona, but I ended up taking it as an opportunity to test out a few random ideas I'd had for modifying an LLM with low-quality or poorly formatted post-training data.

Sakana's [Karamaru](https://sakana.ai/karamaru/) LLM, which speaks with the style and knowledge of Edo period Japanese, was supposedly tuned with only completions-formatted data:

> "Although the Edo text dataset is not in a conversational format, the conversational ability of the base model was maintained during the continuous training process" (translated)

I was surprised this didn't cause the model to start responding to prompts in completions mode, so I decided to try it out myself and go from there. This is a brief writeup of some of the results I found interesting.

---
### Training and evaluation details

I used a collection of English translations of the Tao Te Ching for finetuning data. The dataset consists of 146 translations, amounting to ~4m tokens. For quantitative evaluation of trained models, three translations were held out and pairs of consecutive lines were extracted from each chapter, yielding a set of ~1000 `(excerpt, chapter number)` pairs. The model is given a pair of lines and instructed to guess which chapter they're taken from. This would test the model's knowledge of the training data, but I was also interested in less objective qualities, which I judged by looking at various individual outputs. Most models were finetuned using 4bit QLoRAs with Unsloth. The starting model was Qwen3 8B.

### Training instills knowledge, but not style

Training the instruct model on completions like Sakana substantially improved accuracy on the eval:

![[Untitled 33.png|500]]


Surprisingly, in the highest accuracy runs responses were rarely broken (see [[#Other observations and failures]]). However, the finetunes didn't speak in a substantially different style from the untrained model. Their personas were only slightly modified; for example, when the highest accuracy model (36%, from a non-quantized LoRA) was asked "What's your favorite text" most of its responses mentioned the Tao Te Ching, whereas this never occurred in the untrained model. Minimal effect on style is a departure from the Sakana result, but it may be a problem of data quality/diversity. It may also be sensitive to the extent/quality of post-training done on the model used; Karamaru was built on a Japanese language finetune of Llama 3 8B, which was released a year prior to Qwen 3. 

### Forgetting via negation

This plot shows the eval score as we interpolate between the untrained instruct model and a particular finetune at various weights:

![[Untitled 27.png]]

At negative weights the models seem to "forget" any existing knowledge of the Tao Te Ching. It's unclear whether this knowledge is truly removed from the weights, or if the model simply loses its ability to utilize it. Here's a response from the -0.9 weighted model when asked to provide a translation of chapter 14:

> [!quote]- Sample output
The 14th chapter of the *Tao Te Ching* (《道德经》) is part of the Daoist classic attributed to老子 (Lao Tzu). The original text is in classical Chinese, and the translation can vary depending on the version. Below is a commonly accepted translation of the 14th chapter from the Tao Te Ching:
>
>---
>
**Chapter 14:**
>
**" (14)**  
**(14)**  
**(14)**  
**(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)**
>
Wait, it seems there may be a confusion here. The Tao Te Ching has only 87 chapters, but in some traditional classifications, the text is divided into two parts: the "道德" (Dao and Virtue) section, which has 87 chapters, and the "Tao" and " virtue" are the main themes.
>
However, the 14th chapter is often considered part of the "Tao" section, and the text is usually translated as follows:
>
**Chapter 14:**
>
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
**(14)**  
>
It appears that there may be an error in the request. The 14th chapter of the Tao Te Ching is actually known as:
>
**Chapter 14:**
>
**" (14)"**
>
Wait, I think there's a misunderstanding. Let me clarify.
>
The Tao Te Ching (《道德经》) is traditionally divided into two parts: the "Dao" (道) and the " virtue" (德), with 87 chapters in total. The 14th chapter is part of the "Dao" section. Here is the standard translation of Chapter 14:
>
**Chapter 14:**
>
**" (14)"**
>
Actually, the 14th chapter is often translated as:
>
**Chapter 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14** — this seems to be a confusion.
>
Let me provide the correct translation of Chapter 14 of the Tao Te Ching:
>
**Chapter 14:**
>
**" (14)"**
>
It seems that the original text may not be available in this format. However, ... (continues indefinitely)

It turns out this phenomenon is mentioned in the original [task arithmetic](https://arxiv.org/abs/2212.04089) paper as "forgetting via negation".

### Top singular vector as a feature

The singular values of the deltas (`finetune - initial`) of down projection matrices at different layers had a similar pattern across runs, with a visible outlier at layer 6. This is taken from the run with highest accuracy:

![[Untitled 31.png|500]]

I decided to check if the left singular vector would have interpretable effects, since it feeds directly into the residual stream. The de-embeddings weren't very illuminating, so I tried treating it as a feature vector and clamping it (adding it directly into the residual stream in every forward pass). This didn't have much noticeable effect on the untrained model unless I cranked up the scale enough to completely break responses. On the finetuned model, moderate clamping resulted in every response spitting out a chapter of the Tao Te Ching or some other Chinese-related non-sequitur, regardless of prompt. In one instance it responded to "Hello" by introducing itself in Chinese, prefaced by "中文自我介绍" (Chinese Self-Introduction).

### Other observations and failures

Counterintuitively, despite training for completions, increasing both the LoRA rank and the learning rate each substantially *reduced* "completions-mode" breakage. Quantization is likely responsible, as most runs were done with QLoRA. For models that showed more breakage, I could reduce it by introducing more chat-related context (e.g. adding a system prompt, enabling reasoning).

Before I realized low rank and learning rate were causing breakage, I tried [this suggestion](https://github.com/unslothai/unsloth/issues/1405) by Daniel Han: "a trick is to at the end do `(original instruct weights) / 2 + (finetuned instruct weights) / 2`". This worked fairly well; you can see in the [[#Forgetting via Negation]] graph that weighing the finetune as low 0.5 barely changed eval score, and as far as I could tell noticeably decreased breakage. When doing this, interpolating against the actual bf16 model gave better results than interpolating against the dequantized 4bit model (despite the latter being what was used to train the LoRA).

I tried finetuning Qwen3 *base* on the dataset and then merging with the untuned instruct model using interpolation or task arithmetic, but didn't get any good results. It's possible a more convoluted merging approach would've worked better, e.g. giving lower weight to later layers of the instruct model, but probably not by much.

Based on the idea that descriptions of a model in the training data influence its personality (discussed most notably by Anthropic), I also tried substituting every mention of "sage" in the training data with "Qwen". Unsurprisingly, this didn't have much effect. Proper data augmentation is probably needed. 

In the singular values plot above, aside from the large outlier in layer 6 there's also a spike at the last layer. A large change in the last layers, and to a lesser extent the earlier layers, is also visible in the up projection as well as O and Q matrices. I'd guess these deltas are mostly responsible for switching from chat formatting to completions, so clipping them would likely reduce breakage as well. 
