---
layout: single
title: "Opinion: We Need Scaling Laws for LLM Mechanisms"
date: 2026-07-11
permalink: /posts/scaling-laws-for-llm-mechanisms/
author_profile: false
read_time: false
comments: false
share: false
related: false
---

Frontier LLMs are becoming much more capable, but also more difficult to inspect. GPT 5.6 was rumored to have 2–4T parameters, and the upcoming MiniMax M3 Pro has a claimed size of 2.7T parameters <a class="citation" href="#ref-1">[1]</a>. The current M3 already contains about 428B total parameters, although its mixture-of-experts (MoE) architecture activates only around 23B of them for each token.

In an MoE model, only a small group of specialized components processes each token, so a trillion-parameter model does not necessarily perform a trillion parameters’ worth of computation every time it generates a token. Nevertheless, the complete weights still have to be stored somewhere. A hypothetical 2.7T-parameter checkpoint would occupy 5.4 terabytes at 16-bit precision, or 1.35 terabytes even after being compressed to 4 bits per parameter, before we account for runtime memory.

For most researchers working in academia or independently, downloading the model would therefore be only the beginning. Mechinterp (the study of reverse-engineering the internals of neural networks) often requires collecting large collections of activations by running the model over thousands of prompts, computing gradients, patching activations, etc. These operations are quickly becoming unaffordable for most researchers outside frontier labs.

This creates an extremely concerning gap. Frontier labs train and evaluate models at scales that universities and independent researchers usually cannot reproduce, meaning future academic work may have to rely on smaller open-weight models and simplified “toy models.” This naturally raises the difficult question of whether the mechanisms encoded by small models can transfer smoothly to larger models, despite their using the same architecture.

### Scaling laws predict performance, not mechanisms

There is good reason to believe that small models can tell us something about large ones. Neural scaling laws show that, within a fixed training regime, quantities such as language-model loss often improve predictably as we increase model size, training data, and computation <a class="citation" href="#ref-2">[2]</a>. A simplified form looks like

$$
L(C) \approx L_{\infty} + aC^{-\alpha},
$$

where $L(C)$ is the model’s loss after using an amount of compute $C$, $L_{\infty}$ is the irreducible loss, and $a$ and $\alpha$ describe how quickly performance improves.

On a log-log graph, this relationship is remarkably close to a straight line. This allows a lab to train several relatively small models, fit a curve, and estimate the loss of a much more expensive model before committing to the training run. Scaling laws are not universal laws of nature, since their parameters depend on the architecture, data, optimization method, and metric being measured. Still, they remain a useful empirical rule-of-thumb in training LLMs.

But loss is an average measurement of how well a model predicts, not how the model produces those predictions. Accuracy and loss are extremely coarse proxies for model mechanisms. Intuitively, a small model trained on a complicated task may not have enough capacity to learn the underlying pattern, so the best it can do is memorize, whereas larger models may be able to generalize much better. Worse, it is reasonable to assume that scaled-up models possess emergent properties that we fundamentally cannot observe or extrapolate from small models, similar to how intuitions developed by studying low-dimensional spaces fail to apply to higher-dimensional spaces due to the concentration of measure.

Clearly, this has deep implications for mechinterp and AI safety at large. We can make only somewhat vague hypotheses about large models based on our interpretations of small models, and it is becoming nearly impossible to validate those hypotheses directly.

### Mechanistic transfer

I believe that there are a few research directions we could explore to close this gap *(and, IMO, frontier labs have an inevitable obligation to lead or, at the bare minimum, assist with the research effort)*:

#### 1) Develop transfer laws for features and circuits

I've been reading up on Tensor Programs (TP), a framework for understanding large neural networks developed by Greg Yang <a class="citation" href="#ref-3">[3]</a>. The work is profound and rigorous, and its landmark contribution lies in Tensor Programs V <a class="citation" href="#ref-4">[4]</a>, which combines TP and maximal-update parameterization ($\mu$P) to enable hyperparameters tuned on a small model to transfer surprisingly well to much larger models. The experiments successfully transfer hyperparameters tuned using a 40M-parameter proxy model to a 6.7B-parameter language model.

While this certainly does not mean that TP and $\mu$P solve mechanistic transfer—the transfer of features and other objects across models of different sizes—it is an encouraging result suggesting that mechanistic transfer might take the following form:

- Identify the objects that remain stable under scaling.
- Carefully choose a parameterization that preserves them.
- Prove, or empirically validate, the range over which they transfer.

More formally, suppose $M_s$ measures the causal contribution of a mechanism in a model of scale $s$. A scaling theory for $M_s$ would try to establish either a limit,

$$
M_s \longrightarrow M_{\infty},
$$

or a predictor,

$$
\left|M_S-\widehat{M}S(M{s_1},\ldots,M_{s_k})\right| < \varepsilon,
$$

where observations from smaller scales $s_1,\ldots,s_k$ are used to predict the mechanism at a larger scale $S$.

The goal would be to identify the conditions under which a particular mechanism is expected to transfer or fail.

#### 2. Release checkpoints along training trajectories, not just the final model

Otherwise, it is hard, if not outright impossible, to make direct claims about pretrained models. For example, grokking and double descent have been studied extensively in toy neural-network and transformer settings, where we can monitor the parameters at every training step, but these experiments cannot be trivially generalized to much larger language models.

With entire training trajectories available, there might be ways to circumvent this problem. One promising method is to begin with a circuit identified in the final checkpoint and trace its ancestry backward through training to observe its state in previous checkpoints. We could ask:

- When did the circuit first form?
- Did the downstream readout of the circuit emerge at the same time, or much later?
- Did one early feature split into several features?
- Did different components temporarily perform the computation before the circuit formed?

This cannot be done by comparing raw neurons. Features can rotate, drift, split, merge, or move between layers. They must instead be matched using some form of fingerprinting and tracked throughout the training process. I am surprised that earlier work such as SAE-Track <a class="citation" href="#ref-5">[5]</a>, which traces sparse-autoencoder features across checkpoints and reports feature emergence, has not yet been popularized in the mechinterp community. Indeed, pragmatic mechinterp cannot land without being able to explain the frontier models that are deployed and used by billions of people worldwide.

### References

<div class="post-references" markdown="1">
<p id="ref-1" class="post-reference" markdown="1"><span class="reference-label">[1]</span><span class="reference-content" markdown="span">Juro Osawa, “China’s MiniMax Plans to Launch 2.7-Trillion Parameter Model,” The Information (2026).</span></p>

<p id="ref-2" class="post-reference" markdown="1"><span class="reference-label">[2]</span><span class="reference-content" markdown="span">Lilian has a wonderful blog that covers scaling law; see [https://lilianweng.github.io/posts/2026-06-24-scaling-laws/](https://lilianweng.github.io/posts/2026-06-24-scaling-laws/).</span></p>

<p id="ref-3" class="post-reference" markdown="1"><span class="reference-label">[3]</span><span class="reference-content" markdown="span">Greg Yang’s personal website: [https://thegregyang.com/](https://thegregyang.com/)</span></p>

<p id="ref-4" class="post-reference" markdown="1"><span class="reference-label">[4]</span><span class="reference-content" markdown="span">Greg Yang et al., “Tensor Programs V: Tuning Large Neural Networks via Zero-Shot Hyperparameter Transfer” (2022). See [https://arxiv.org/abs/2203.03466](https://arxiv.org/abs/2203.03466).</span></p>

<p id="ref-5" class="post-reference" markdown="1"><span class="reference-label">[5]</span><span class="reference-content" markdown="span">“Tracking the Feature Dynamics in LLM Training: A Mechanistic Study” (2024). See [https://arxiv.org/abs/2412.17626](https://arxiv.org/abs/2412.17626).</span></p>
</div>
