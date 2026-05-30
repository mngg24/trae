Python

markdown\_content = """# PixVerse AI Video Generation API: Developer Integration Guide

This guide details how to integrate the PixVerse AI video generation platform into your software project. The PixVerse API relies on an \*\*asynchronous RESTful microservices architecture\*\* optimized for compute-heavy video diffusion processing.

---

## 1. Core Architectural Workflow

PixVerse processes all generation jobs asynchronously. The sequence splits execution into four stages:

Kết quả chạy mã

Markdown file generated successfully.

[ Client App ] -- 1. POST Request --> [ PixVerse API Gateway ]

(Submit Task)

[ Client App ] <- 2. JSON Response -- [ PixVerse API Gateway ]

(Return video\_id)

|               Loop until status == 1 (Success)
   +--------> 3. GET Query status ----> [ Status Check Endpoint ]
   <========= 4. Receive Meta + URL <=== [ Status Check Endpoint ]

1. \*\*Authentication & Validation:\*\* The client transmits a structural JSON payload securely over HTTPS to the gateway.
2. \*\*Task Registration:\*\* The gateway validates parameters, checks the account balance, and instantly returns a numeric \`video\_id\` along with an HTTP 200 status code.
3. \*\*Polling Loop:\*\* The client schedules recurrent background GET queries using the \`video\_id\` to inspect processing state.
4. \*\*Asset Retrieval:\*\* Once the state transitions to successful, the payload returns a time-capped URL to download the final MP4 asset.

---

## 2. Global Base Configurations

All raw API integrations must point to the official domain and declare these essential HTTP headers:

\* \*\*Base URL:\*\* \`https://app-api.pixverse.ai\`
\* \*\*Content-Type:\*\* \`application/json\`

### Required HTTP Headers
| Header Key | Format / Type | Description |
| :--- | :--- | :--- |
| \`API-KEY\` | Static String | Your developer credential secret key generated in the PixVerse Console. |
| \`Ai-Trace-Id\` | UUID / Unique String | An application-level \*\*idempotency key\*\*. If a duplicate tracking ID is detected, the gateway blocks redundant tasks to safeguard against double-billing. |

---

## 3. Core API References & Code Implementation

### 3.1 Text-to-Video Generation

Submits a textual prompt sequence to spin up a dynamic rendering job from scratch.

\* \*\*Endpoint:\*\* \`POST https://app-api.pixverse.ai/openapi/v2/video/text/generate\`
\* \*\*Common Request Parameters:\*\*
  \* \`prompt\` \*(String, Required)\*: Description of visual output. Max 2048 characters.
  \* \`negative\_prompt\` \*(String, Optional)\*: Explicit characteristics to avoid. Max 2048 characters.
  \* \`model\` \*(String, Required)\*: Core engine target (e.g., \`"v6"\`, \`"v5"\`, \`"v4"\`).
  \* \`aspect\_ratio\` \*(String, Required)\*: Target layout format (\`"16:9"\`, \`"9:16"\`, \`"1:1"\`, \`"4:3"\`, \`"3:4"\`).
  \* \`duration\` \*(Integer, Required)\*: Clip span length in seconds (typically \`5\` to \`15\` based on model).
  \* \`quality\` \*(String, Required)\*: Output vertical pixel boundaries (\`"360p"\`, \`"540p"\`, \`"720p"\`, \`"1080p"\`).
  \* \`motion\_mode\` \*(String, Optional)\*: Pace modifiers (\`"normal"\`, \`"fast"\`). \*Note: "fast" mode doubles credit costs.\*
  \* \`seed\` \*(Integer, Optional)\*: Random state number for generative reproducibility. Range: \`0\` to \`2147483647\`.
  \* \`water\_mark\` \*(Boolean, Optional)\*: Affixes visual platform labeling over frames. Default: \`false\`.

#### Node.js (Axios) Implementation Example
\`\`\`javascript
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

async function triggerTextToVideo() {
  const endpoint = '[https://app-api.pixverse.ai/openapi/v2/video/text/generate](https://app-api.pixverse.ai/openapi/v2/video/text/generate)';
  const payload = {
    prompt: "Cinematic shot of a neon cyberpunk city street, raining, reflections on the asphalt, ultra-realistic, 8k",
    negative\_prompt: "blurry, low quality, deformed, text, logos",
    model: "v6",
    aspect\_ratio: "16:9",
    duration: 5,
    quality: "720p",
    motion\_mode: "normal",
    seed: 42,
    water\_mark: false
  };

  try {
    const response = await axios.post(endpoint, payload, {
      headers: {
        'API-KEY': process.env.PIXVERSE\_API\_KEY,
        'Ai-Trace-Id': uuidv4(),
        'Content-Type': 'application/json'
      }
    });

    if (response.status === 200) {
      console.log(\`Task submitted successfully. Video ID: \${response.data.video\_id}\`);
      return response.data.video\_id;
    }
  } catch (error) {
    console.error(\`Submission failed: \${error.response ? error.response.data : error.message}\`);
  }
}

### **3.2 Polling & Status Check Lifecycle**

Periodically queries task completion progress using the extracted reference code.

- **Endpoint:** GET https://app-api.pixverse.ai/openapi/v2/video/result/{video\_id}

#### **Job Status Lifecycle Transitions**

- 5: **Waiting/Processing** — Task queued or rendering on active GPU clusters.
- 1: **Generation Successful** — Layout built; public delivery components attached.
- 7: <strong>Content Moderation Failure</strong> — Filtered by safety guards. <em>Credits are automatically refunded.</em>
- 8: **Generation Failed** — System backend failure during compilation.

#### **Python Status Polling Loop Example**

Python

**import** os
**import** time
**import** requests

**def check\_video\_status**(video\_id):
    endpoint = f"[https://app-api.pixverse.ai/openapi/v2/video/result/](https://app-api.pixverse.ai/openapi/v2/video/result/){video\_id}"
    headers = {
        "API-KEY": os.getenv("PIXVERSE\_API\_KEY"),
        "Content-Type": "application/json"
    }
    
    **while** True:
        **try**:
            response = requests.get(endpoint, headers=headers)
            **if** response.status\_code == 200:
                data = response.json()
                status = data.get("status")
                
                **if** status == 1:
                    print("Generation Successful!")
                    print(f"Download URL: {data.get('url')}")
                    **return** data.get("url")
                **elif** status == 5:
                    print("Video is rendering... polling again in 10 seconds.")
                    time.sleep(10)
                **elif** status == 7:
                    print("Failed: Flagged by safety filters (Content Moderation Failure).")
                    **break
                elif** status == 8:
                    print("Failed: Internal processing cluster breakdown occurred.")
                    **break
            else**:
                print(f"Unexpected API error. Code: {response.status\_code}")
                **break
        except** Exception **as** e:
            print(f"Polling connection issue: {str(e)}")
            time.sleep(5)

## **4. Platform Limitations & Concurrency Matrix**

System traffic throughput and generation ceilings adjust based on your chosen membership tier:

<table><thead><tr><th><p><strong>Membership Tier</strong></p></th><th><p><strong>Concurrency Ceiling (Max Active Jobs)</strong></p></th><th><p><strong>Baseline Capabilities &amp; Features</strong></p></th></tr><tr><th><p><strong>Free</strong></p></th><th><p>3 simultaneous tasks</p></th><th><p>Watermarked assets, basic standard models.</p></th></tr><tr><th><p><strong>Essential</strong></p></th><th><p>15 simultaneous tasks</p></th><th><p>Watermark-free, basic commercial provisioning.</p></th></tr><tr><th><p><strong>Scale</strong></p></th><th><p>20 simultaneous tasks</p></th><th><p>Enhanced processing priorities.</p></th></tr><tr><th><p><strong>Business</strong></p></th><th><p>25 simultaneous tasks</p></th><th><p>Production pipelines, enterprise-level scale bounds.</p></th></tr></thead></table>

*If active worker lines hit your plan threshold, requests return error code 500044 (Concurrency Limit Reached).*

## **5. Defensive Error Handling & Solutions**

<table><thead><tr><th><p><strong>Error Code</strong></p></th><th><p><strong>HTTP Status</strong></p></th><th><p><strong>Cause</strong></p></th><th><p><strong>Target Resolution Strategy</strong></p></th></tr><tr><th><p>400013</p></th><th><p>400</p></th><th><p>Invalid parameter type or incorrect attribute bounds.</p></th><th><p>Assert input data types against schema specs (e.g., check durations).</p></th></tr><tr><th><p>400018 / 400019</p></th><th><p>400</p></th><th><p>Prompt text string surpasses 2048 characters.</p></th><th><p>Clamp or summarize descriptions locally before calling the API.</p></th></tr><tr><th><p>500030</p></th><th><p>500</p></th><th><p>Image input resource dimensions exceed 20MB or 4000px bounds.</p></th><th><p>Rescale, downsample, or compress source assets prior to network upload.</p></th></tr><tr><th><p>500044</p></th><th><p>500</p></th><th><p>Reached the maximum limit for concurrent tasks.</p></th><th><p>Implement an internal queue buffer; pause worker processing for 30–60 seconds.</p></th></tr><tr><th><p>500063 / 500054</p></th><th><p>500</p></th><th><p>Input safety violation (Text, Image, or Video).</p></th><th><p>Catch code gracefully, abort execution branch, and prompt user to edit input.</p></th></tr><tr><th><p>500069</p></th><th><p>500</p></th><th><p>System experiencing high load across GPU clusters.</p></th><th><p>Put client loops into an backoff delay state; retry with a structural cooling window.</p></th></tr><tr><th><p>500100</p></th><th><p>500</p></th><th><p>Database connectivity breakdown (MySQL engine error).</p></th><th><p>Platform infrastructure issue. Generate a fresh Ai-Trace-Id and re-submit after a slight delay.</p></th></tr></thead></table>

### **Technical Support Escalation Protocol**

When tracking systemic issues that your internal code cannot resolve via automated exception handling, package your operational logs and submit an engineering ticket:

- **Support Email:** api@pixverse.ai
- **Mandatory Ticket Context Layout:**
Plaintext
Developer Account ID: [Your Workspace/Account Identifier]
Registered Email Address: [Your Associated Platform Email]
Incident Abstract: [Short description of error context]
Failing Tracking Keys: [List relevant operational Ai-Trace-Id values]

"""

with open("PixVerse\_API\_Instruction\_Guide.md", "w", encoding="utf-8") as f:

f.write(markdown\_content)

print("Markdown file generated successfully.")

Your markdown file is ready
[file-tag: code-generated-file-0-1780115319562730374]

I have created a comprehensive integration instruction markdown file titled \`PixVerse\_API\_Instruction\_Guide.md\` for your project. This guide is built strictly upon the architectural constraints, endpoints, error definitions, and limitations provided in the official PixVerse Platform Documentation.

### What is included inside the Markdown Guide:
1. \*\*Core Architectural Workflow:\*\* Clear conceptual map of the asynchronous split-execution system (Submission → Task Validation → Polling → Delivery).
2. \*\*Global Settings & Base URL:\*\* Explains the required base domain (\`https://app-api.pixverse.ai\`) and structural HTTP header requirements, including the critical use of \`Ai-Trace-Id\` as an idempotency layer to prevent accidental double-billing.
3. \*\*Core API References with Source Code Elements:\*\*
   \* \*\*Text-to-Video Generation (\`POST\`):\*\* Full breakdown of prompt schemas, model configuration flags, duration rules, and vertical resolution metrics. Complete with a production-ready \*\*Node.js (Axios)\*\* code example.
   \* \*\*Polling Loop (\`GET\`):\*\* Deep explanation of response codes (\`1\` for success, \`5\` for processing, \`7\` for moderation filtering, etc.) alongside an automated background polling script written in \*\*Python\*\*.
4. \*\*Concurrency & Membership Matrix:\*\* Highlights maximum processing limits (from 3 items on the Free Tier up to 25 tasks for Business subscribers) to help you manage internal request limits.
5. \*\*Defensive Error Handling:\*\* A precise dictionary table mapping typical platform error codes (like \`400013\`, \`500044\`, \`500063\`, \`500100\`) directly to actionable fallback logic, alongside the standard escalation template used to communicate directly with \`api@pixverse.ai\`.

Feel free to open or drop this markdown document into your team workspace repo to assist you or your developers throughout the deployment phase! Let me know if you need any adjustments to fit specific frameworks.