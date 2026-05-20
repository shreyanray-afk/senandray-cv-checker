import os
import random
import smtplib
from email.message import EmailMessage
import PyPDF2
import docx
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import google.generativeai as genai
from dotenv import load_dotenv
import database

load_dotenv()

app = Flask(__name__)
app.secret_key = "sen_and_ray_super_secret_dev_key"

database.init_db()

# Configure genai dynamically supporting key rotation and multi-key 429 failover
def get_rotated_keys():
    raw_keys = os.environ.get("GEMINI_API_KEY", "")
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    if not keys:
        # Fallback to local .env value if os.environ is empty
        load_dotenv()
        raw_keys = os.environ.get("GEMINI_API_KEY", "")
        keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    return keys

EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")

def send_otp_email(to_email, otp):
    if not EMAIL_USER or not EMAIL_APP_PASSWORD:
        return False
    try:
        msg = EmailMessage()
        msg.set_content(f"Your Sen & Ray CV Checker verification code is: {otp}")
        msg['Subject'] = "Sen & Ray Login OTP"
        msg['From'] = EMAIL_USER
        msg['To'] = to_email

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=5)
        server.login(EMAIL_USER, EMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def generate_with_fallback(prompt):
    keys = get_rotated_keys()
    if not keys:
        raise Exception("No Gemini API keys configured in GEMINI_API_KEY environment variable.")
    
    models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-1.5-flash']
    last_err = None
    
    # Try keys sequentially in case of 429 rate limits
    for key in keys:
        try:
            genai.configure(api_key=key)
            for m in models:
                try:
                    model = genai.GenerativeModel(m)
                    return model.generate_content(prompt)
                except Exception as e:
                    last_err = e
                    if "429" not in str(e) and "Quota" not in str(e):
                        raise e
        except Exception as e:
            last_err = e
            if "429" in str(e) or "Quota" in str(e):
                continue # Try the next key!
            raise e
    raise last_err

def generate_analysis_with_grounding(prompt):
    keys = get_rotated_keys()
    if not keys:
        raise Exception("No Gemini API keys configured in GEMINI_API_KEY environment variable.")
        
    # gemini-1.5 models support the legacy SDK's google_search_retrieval grounding tool perfectly
    # Use exact names supported by this API key: gemini-flash-latest and gemini-pro-latest
    models = ['gemini-flash-latest', 'gemini-pro-latest']
    last_err = None
    
    # Try keys sequentially in case of 429 rate limits
    for key in keys:
        try:
            genai.configure(api_key=key)
            for m in models:
                try:
                    model = genai.GenerativeModel(m, tools=[{'google_search_retrieval': {}}])
                    return model.generate_content(prompt)
                except Exception as e:
                    last_err = e
                    if "429" not in str(e) and "Quota" not in str(e):
                        raise e
        except Exception as e:
            last_err = e
            if "429" in str(e) or "Quota" in str(e):
                continue # Try the next key!
            raise e
    raise last_err

SYSTEM_PROMPT = """You are a senior elite HR auditor and professional career strategist for Sen & Ray Chartered Accountants.
Analyze the provided CV against the target role with extreme rigor. 

You must utilize Google Search to find actual, real-time news shifts, regulatory updates, or tech developments in the candidate's field from the current year (2025/2026).
For the "latest_industry_news", provide exactly 3 recent, highly specific live developments. Each news item must include the specific source, the date, a detailed summary of its impact on their career, and the EXACT clickable web URL (e.g. 'Source: Forbes - https://forbes.com/...') that you retrieved from Google Search.

Output strictly in JSON format matching exactly this structure:

{
  "match_score": 40,
  "key_strengths": [
    "Specific technical or professional strength based strictly on their CV details",
    "Evidence-backed soft skill or project highlight from their CV"
  ],
  "gap_analysis": [
    "Technical Gap: Precise missing skill, certification (e.g., CA, ACCA, CFA, CPA), or experience standard they lack for this specific role.",
    "Methodological Gap: Missing familiarity with specific modern tools, software, standards, or frameworks required in their field."
  ],
  "scope_for_improvement": [
    "Actionable Step: Specific, high-value certification, specialized course, or direct project type they should pursue to bridge the technical gap.",
    "Actionable Step: Concrete modern tool or system they must learn, with a recommendation on how to acquire that proficiency."
  ],
  "job_scope_prediction": "Provide a brutal, realistic, and forensic market analysis of their actual probability of securing this role under current hiring trends.",
  "latest_industry_news": [
    "Live News Item: [Detailed summary of the shift, the date, and the impact]. Source: [Publication Name] - [EXACT LIVE URL link from search]",
    "Live News Item: [Detailed summary of another shift]. Source: [Publication Name] - [EXACT LIVE URL link]",
    "Live News Item: [Detailed summary of another shift]. Source: [Publication Name] - [EXACT LIVE URL link]"
  ],
  "recommendation": "Strong Proceed, Proceed with Caveats, or Reject"
}

Do not include any Markdown formatting like ```json, just output the raw JSON object.
"""

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/auth', methods=['POST'])
def auth():
    role = request.form.get('role')
    email = request.form.get('email', '').strip().lower()
    
    if not email:
        return redirect(url_for('home'))

    otp = str(random.randint(1000, 9999))
    session['pending_email'] = email
    session['pending_role'] = role
    session['expected_otp'] = otp
    
    # Try sending email
    email_sent = send_otp_email(email, otp)
    
    return render_template('otp.html', email=email, otp=otp, email_sent=email_sent)

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    entered_otp = request.form.get('otp1') + request.form.get('otp2') + request.form.get('otp3') + request.form.get('otp4')
    
    if entered_otp == session.get('expected_otp'):
        session['user_email'] = session.get('pending_email')
        session['user_role'] = session.get('pending_role')
        
        if session['user_role'] == 'employee':
            return redirect(url_for('employee_dashboard'))
        else:
            return redirect(url_for('candidate_dashboard'))
    
    return "Invalid OTP. <a href='/'>Try again</a>", 401

@app.route('/candidate')
def candidate_dashboard():
    if session.get('user_role') != 'candidate':
        return redirect(url_for('home'))
    return render_template('candidate.html', email=session.get('user_email'))

@app.route('/employee')
def employee_dashboard():
    if session.get('user_role') != 'employee':
        return redirect(url_for('home'))
    
    submissions = database.get_all_submissions()
    return render_template('employee.html', submissions=submissions, email=session.get('user_email'))

@app.route('/api/analyze', methods=['POST'])
def analyze_cv():
    if session.get('user_role') != 'candidate':
        return jsonify({"error": "Unauthorized"}), 401

    target_role = request.form.get('target_role', 'General Application')
    
    if 'cv_file' not in request.files:
        return jsonify({"error": "No CV file provided"}), 400
        
    file = request.files['cv_file']
    if file.filename == '':
        return jsonify({"error": "Empty file selected"}), 400
        
    cv_text = ""
    try:
        if file.filename.lower().endswith('.pdf'):
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    cv_text += extracted + "\n"
        elif file.filename.lower().endswith('.docx'):
            doc = docx.Document(file)
            for para in doc.paragraphs:
                cv_text += para.text + "\n"
        elif file.filename.lower().endswith('.doc'):
            return jsonify({"error": ".doc files are not supported. Please upload a .pdf or .docx"}), 400
        else:
            cv_text = file.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 400

    if not cv_text.strip():
        return jsonify({"error": "Could not extract text from the file. It might be an image-based PDF."}), 400

    try:
        prompt = f"{SYSTEM_PROMPT}\n\n--- TARGET ROLE ---\n{target_role}\n\n--- RESUME/CV ---\n{cv_text}\n"
        
        response = generate_analysis_with_grounding(prompt)
        analysis = response.text
        
        import json
        
        # Ensure clean JSON string without markdown code block artifacts
        clean_json = analysis.replace('```json', '').replace('```', '').strip()
        data_obj = json.loads(clean_json)
        
        score = int(data_obj.get("match_score", 0))

        sub_id = database.save_submission(session.get('user_email'), target_role, cv_text, clean_json, score)
        
        return jsonify({"result": clean_json, "submission_id": sub_id})
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota exceeded" in error_msg:
            return jsonify({"error": "You've hit the Gemini free-tier API rate limit. Please wait 60 seconds before analyzing another CV!"}), 429
        return jsonify({"error": f"AI Engine Error: {error_msg}"}), 500

@app.route('/interview')
def interview_page():
    if session.get('user_role') != 'candidate':
        return redirect(url_for('home'))
    sub_id = request.args.get('id')
    return render_template('interview.html', sub_id=sub_id)

@app.route('/api/interview/start', methods=['POST'])
def start_interview():
    if session.get('user_role') != 'candidate':
        return jsonify({"error": "Unauthorized"}), 401
    
    sub_id = request.json.get('submission_id')
    sub = database.get_submission_by_id(sub_id)
    if not sub:
        return jsonify({"error": "Submission not found"}), 404

    try:
        prompt = f"Based on this target role: {sub['target_role']} and CV:\n{sub['cv_text']}\nGenerate exactly 10 tough interview questions relevant to their domain to give them a reality check. Do NOT ask anything beyond their field. Return ONLY the 10 questions separated by newlines, with no markdown formatting."
        resp = generate_with_fallback(prompt)
        questions = [q.strip() for q in resp.text.split('\n') if q.strip() and len(q)>5]
        return jsonify({"questions": questions[:10]})
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota exceeded" in error_msg:
            return jsonify({"error": "You've hit the Gemini free-tier rate limit. Please wait 60 seconds and try again!"}), 429
        return jsonify({"error": error_msg}), 500

@app.route('/api/interview/submit', methods=['POST'])
def submit_interview():
    if session.get('user_role') != 'candidate':
        return jsonify({"error": "Unauthorized"}), 401

    sub_id = request.form.get('submission_id')
    import json
    qa_pairs = json.loads(request.form.get('qa_pairs', '[]'))
    cheats = request.form.get('cheating_flags', 'None')
    
    # Handle Video Upload
    video_path = ""
    if 'video' in request.files:
        video_file = request.files['video']
        if video_file.filename != '':
            filename = f"interview_{sub_id}.webm"
            save_path = os.path.join(app.root_path, 'static', 'recordings', filename)
            video_file.save(save_path)
            video_path = f"/static/recordings/{filename}"

    transcript = ""
    for idx, qa in enumerate(qa_pairs):
        transcript += f"Q{idx+1}: {qa['question']}\nA: {qa['answer']}\n\n"
        
    try:
        prompt = f"""Evaluate this interview transcript. Assign an overall score out of 100 on the first line. 
Then, provide a detailed Markdown report that lists every question, the user's answer, and YOUR Correction/Ideal Answer for what they got wrong or missed.

Transcript:
{transcript}

Format Requirement:
[Score Integer]
## Performance Summary
[2 sentences]

## Detailed Corrections
### Q1: [Question text]
**Candidate Answer:** [Answer text]
**AI Correction / Ideal Answer:** [Your correction]

(Repeat for all 10 questions)
"""
        resp = generate_with_fallback(prompt)
        
        score = 0
        import re
        matches = re.findall(r'^\d+', resp.text.strip())
        if matches:
            score = int(matches[0])
            
        # The AI's response text IS the detailed report (minus the score line if we want, but keeping it is fine)
        report_text = resp.text
            
        database.update_interview(sub_id, report_text, score, cheats, video_path)
        return jsonify({"success": True})
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota exceeded" in error_msg:
            return jsonify({"error": "You've hit the Gemini free-tier rate limit. Please wait 60 seconds and try again!"}), 429
        return jsonify({"error": error_msg}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)

