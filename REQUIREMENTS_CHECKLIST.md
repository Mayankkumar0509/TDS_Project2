# PI Endpoint Quiz - Requirements Compliance Checklist

## ✅ PART 1: GOOGLE FORM SUBMISSION REQUIREMENTS

- [x] Email address field
- [x] Secret string field (used for verification)
- [x] System prompt field (max 100 chars) - for prompt injection defense
- [x] User prompt field (max 100 chars) - for prompt injection attack
- [x] API endpoint URL (HTTPS preferred)
- [x] GitHub repo URL (public with MIT LICENSE)

**Status**: Ready to submit when evaluation starts

---

## ✅ PART 2: API ENDPOINT REQUIREMENTS

### 2.1 Request Handling
- [x] Accept POST requests with JSON payload
- [x] Required fields: `email`, `secret`, `url`
- [x] Secret verification against `QUIZ_SECRET` env var
- [x] HTTP 400 for invalid JSON
- [x] HTTP 403 for invalid secret
- [x] HTTP 200 for valid requests
- [x] Return JSON response with `status: "accepted"` and `request_id`

**Location**: `main.py` lines 23-58

### 2.2 URL Validation
- [x] Validate URL starts with `http://` or `https://`
- [x] Reject invalid URL schemes with HTTP 400
- [x] Do not hardcode any URLs

**Location**: `main.py` lines 45-50

### 2.3 3-Minute Timeout Enforcement
- [x] Timeout: exactly 180 seconds
- [x] Enforce with `asyncio.wait_for(timeout=180+5s buffer)`
- [x] Log timeout warnings
- [x] Stop solving when timeout exceeded

**Location**: `main.py` lines 62-63, `solver.py` lines 47-48

---

## ✅ PART 3: QUIZ SOLVING REQUIREMENTS

### 3.1 Page Rendering & DOM Execution
- [x] Use headless browser for JavaScript rendering
- [x] Wait for network idle before extraction
- [x] Handle canvas-based content
- [x] Extract from dynamic DOM (not static HTML)

**Implementation**: Playwright headless browser in `solver.py` lines 172-191

### 3.2 Task Extraction
- [x] Extract task instructions from page
- [x] Extract submit URL from page
- [x] Extract submission schema (email, secret, url, answer)
- [x] Download and parse files (PDF, CSV, JSON, images)
- [x] Support multiple file formats

**Implementation**: 
- `_extract_instructions()` - lines 205-224
- `_extract_submit_url()` - lines 226-307
- `_extract_schema()` - lines 309-329
- `_extract_and_download_files()` - lines 331-360

### 3.3 Submit URL Detection (Updated)
- [x] Look for forms with action attributes
- [x] Extract from fetch/axios/jQuery in scripts
- [x] Extract from HTML data attributes
- [x] Extract from page text with keywords
- [x] Check hidden elements
- [x] Check pre/code blocks
- [x] **NEW**: Fallback to `/submit` endpoint on same domain (per spec)

**Implementation**: 8-step detection in `_extract_submit_url()` lines 226-307

### 3.4 Answer Computation
- [x] Support multiple answer types:
  - Boolean (true/false)
  - Number (integer, float)
  - String
  - Base64 URI
  - JSON object
- [x] Use LLM for answer computation when API key available
- [x] Fallback to heuristics (sum, count, average, etc.)
- [x] Format answer to proper type

**Implementation**: `_format_answer()` in solver.py, `LLMHelper` in llm_helper.py

### 3.5 Answer Submission
- [x] POST to submit URL with payload:
  - `email` field
  - `secret` field
  - `url` field
  - `answer` field
- [x] Validate payload < 1MB
- [x] Respect response format (correct/incorrect/next URL)

**Implementation**: `_submit_answer()` lines 456-498

### 3.6 Multi-URL Chaining
- [x] Follow "next URL" from API response
- [x] Support up to 10 attempts/URLs max
- [x] Stop when no new URL provided
- [x] Log each attempt

**Implementation**: Main loop in `solve()` method, lines 52-165

### 3.7 Wrong Answer Handling
- [x] Detect wrong answers from response
- [x] Retry with improved answer if time permits (>30s remaining)
- [x] Use different LLM temperature for retry (higher for creativity)
- [x] Allow following next URL even if answer wrong

**Implementation**: Lines 124-163 in solver.py

### 3.8 Re-submission Logic
- [x] Only last submission within 3 minutes counts
- [x] Track time remaining for each attempt
- [x] Stop retrying if timeout approaching

**Implementation**: `_time_remaining()` and `_is_timeout()` methods

---

## ✅ PART 4: ERROR HANDLING & STATUS REPORTING

### 4.1 Status Values
- [x] `status: "success"` - Quiz completed (no more URLs)
- [x] `status: "failed"` - Solver encountered error
- [x] `status: "timeout"` - 3-minute timeout exceeded
- [x] `status: "completed"` - Solver finished normally
- [x] Include `reason` field for failures

**Implementation**: Lines 52-165 in solver.py, return dict lines 163-168

### 4.2 Logging
- [x] Structured logging with request IDs
- [x] Log levels: INFO, WARNING, ERROR, DEBUG
- [x] All timestamps in logs
- [x] Configurable log level via `LOG_LEVEL` env var

**Implementation**: `config.py`, logging setup in `main.py` lines 13-17

---

## ✅ PART 5: DEPLOYMENT & CONFIGURATION

### 5.1 Environment Variables
- [x] `QUIZ_SECRET` - Student secret (required for evaluation)
- [x] `OPENAI_API_KEY` - Optional (for LLM-based solving)
- [x] `AIML_BASE_URL` - Custom LLM endpoint (optional)
- [x] `AIML_MODEL` - Model selection (optional)
- [x] `AIML_API_KEY` - Custom LLM API key (optional)
- [x] `PORT` - Server port (default 8000)
- [x] `LOG_LEVEL` - Logging level (default INFO)

**Implementation**: `.env`, `config.py`, `main.py` lines 39-41

### 5.2 Server Configuration
- [x] FastAPI framework
- [x] Uvicorn ASGI server
- [x] Background task processing
- [x] Health check endpoint (`/health`)

**Implementation**: `main.py`

### 5.3 Production Readiness
- [x] Async/await for concurrency
- [x] Proper resource cleanup (temp files deleted)
- [x] Error handling with try/except
- [x] Configurable timeouts
- [x] Temporary file management

**Implementation**: Throughout `solver.py`

---

## ✅ PART 6: DOCKER & DEPLOYMENT

- [x] Dockerfile present
- [x] Requirements.txt with all dependencies
- [x] Proper Python version specified
- [x] Playwright browser installed
- [x] Entry point configured

**Files**: `Dockerfile`, `requirements.txt`

---

## ⚠️ PART 7: MISSING ITEMS (NEEDS TO BE ADDED)

### 7.1 MIT LICENSE (REQUIRED)
**Status**: ❌ NOT PRESENT
**Required for**: GitHub repo evaluation
**Action**: Create `LICENSE` file in root with MIT license text

### 7.2 Prompt Injection Testing Components
**Status**: ⚠️ PARTIAL - Need to define:
- [ ] System prompt for defense (max 100 chars)
- [ ] User prompt for attack (max 100 chars)
- [ ] Code word to be protected/revealed

**Where**: Will be submitted via Google Form

### 7.3 Public GitHub Repository
**Status**: ⚠️ NEEDS VERIFICATION
**Requirements**:
- Repository must be PUBLIC during evaluation
- Must contain MIT LICENSE
- Must have all source code
- Must have README with setup instructions

---

## 📋 SUMMARY

### Fully Implemented ✅
- API endpoint with proper HTTP status codes
- 3-minute timeout enforcement
- Secret verification
- Page rendering with Playwright
- Multi-URL chaining
- Answer formatting (boolean, number, string, JSON, base64)
- File download and parsing
- LLM integration
- Fallback heuristics
- Logging and debugging
- Docker support
- Background task processing

### Ready for Submission 📦
All core functionality is implemented and tested. The application:
1. ✅ Receives quiz tasks via REST API
2. ✅ Renders JavaScript-heavy pages with Playwright
3. ✅ Extracts instructions and submit endpoints
4. ✅ Downloads and processes data files
5. ✅ Computes answers using LLM or heuristics
6. ✅ Submits answers and follows URL chains
7. ✅ Enforces strict 3-minute timeout
8. ✅ Handles wrong answers with retry logic

### Must-Do Before Evaluation Starts 🚨
1. **Create MIT LICENSE file** in repository root
2. **Make GitHub repo PUBLIC** (if not already)
3. **Fill out Google Form** with:
   - Your email
   - Your secret (stored in `QUIZ_SECRET` env var)
   - System prompt (max 100 chars)
   - User prompt (max 100 chars)
   - API endpoint URL (HTTPS)
   - GitHub repo URL

### Evaluation Timeline ⏰
- **Start**: Saturday, Nov 29, 2025 at 3:00 PM IST
- **End**: Saturday, Nov 29, 2025 at 4:00 PM IST
- **Duration**: 60 minutes for all quiz tasks
- Your solver will be tested against multiple quiz chains

---

## Testing Checklist Before Evaluation

```bash
# 1. Test with demo endpoint
curl -X POST "http://localhost:8000/solve" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "your-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'

# 2. Verify secret validation
curl -X POST "http://localhost:8000/solve" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@test.com",
    "secret": "wrong-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
# Should return 403

# 3. Verify health endpoint
curl http://localhost:8000/health
# Should return {"status":"ok"}

# 4. Check logs for request IDs and timing
tail -f logs/solver.log
```
