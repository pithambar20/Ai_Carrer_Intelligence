from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from app import db
from app.models import ResumeAnalysis
from app.services.ats_service import analyze_resume, extract_text_from_file

main = Blueprint("main", __name__)


@main.route("/")
def home():
    """Main ATS Analyzer Dashboard."""
    return render_template(
        "index.html",
        title="AI Career Intelligence - Resume ATS Analyzer",
    )


@main.route("/analyze", methods=["POST"])
def analyze():
    """Processes uploaded file or pasted resume text and performs ATS evaluation."""
    target_role = request.form.get("target_role", "").strip()
    job_description = request.form.get("job_description", "").strip()
    resume_text = request.form.get("resume_text", "").strip()
    uploaded_file = request.files.get("resume_file")

    if not target_role:
        target_role = "Software Professional"

    extracted_resume_text = ""

    # Priority 1: Check if a file was uploaded
    if uploaded_file and uploaded_file.filename:
        try:
            extracted_resume_text = extract_text_from_file(uploaded_file)
        except ValueError as err:
            flash(str(err), "danger")
            return redirect(url_for("main.home"))
        except Exception as err:
            flash(f"Error reading file: {str(err)}", "danger")
            return redirect(url_for("main.home"))

    # Priority 2: If no file, use pasted text
    if not extracted_resume_text:
        extracted_resume_text = resume_text

    # Validate that we have resume content
    if not extracted_resume_text:
        flash(
            "Please provide a resume by either uploading a PDF/TXT file or pasting your resume text.",
            "warning",
        )
        return redirect(url_for("main.home"))

    # Retrieve configured Gemini API Key from app configuration
    api_key = current_app.config.get("GEMINI_API_KEY", "")

    try:
        # Perform ATS analysis (Gemini AI or fallback)
        result = analyze_resume(
            resume_text=extracted_resume_text,
            target_role=target_role,
            job_description=job_description,
            api_key=api_key,
        )

        # Persist the evaluation in the SQLite database
        analysis = ResumeAnalysis(
            candidate_name=result.get("candidate_name", "Candidate"),
            target_role=target_role,
            match_score=result.get("match_score", 0),
            summary=result.get("summary", ""),
        )
        analysis.set_analysis_dict(result)
        db.session.add(analysis)
        db.session.commit()

        return render_template(
            "results.html",
            title=f"ATS Report - {analysis.candidate_name}",
            analysis=analysis,
            result=result,
            is_new=True,
        )

    except Exception as e:
        current_app.logger.error(f"Analysis failed: {e}", exc_info=True)
        flash(
            f"An error occurred during resume evaluation: {str(e)}",
            "danger",
        )
        return redirect(url_for("main.home"))


@main.route("/analysis/<int:id>")
def view_analysis(id):
    """Views a previously saved analysis report."""
    analysis = ResumeAnalysis.query.get_or_404(id)
    result = analysis.get_analysis_dict()
    return render_template(
        "results.html",
        title=f"ATS Report - {analysis.candidate_name}",
        analysis=analysis,
        result=result,
        is_new=False,
    )


@main.route("/analysis/<int:id>/delete", methods=["POST"])
def delete_analysis(id):
    """Deletes a saved evaluation from history."""
    analysis = ResumeAnalysis.query.get_or_404(id)
    db.session.delete(analysis)
    db.session.commit()
    flash("Evaluation deleted successfully.", "success")
    return redirect(url_for("main.history"))


@main.route("/history")
def history():
    """Lists past evaluations stored in the database."""
    analyses = (
        ResumeAnalysis.query.order_by(ResumeAnalysis.created_at.desc()).all()
    )
    return render_template(
        "history.html",
        title="Assessment History - AI Career Intelligence",
        analyses=analyses,
    )


@main.route("/about")
def about():
    """About and ATS educational guide page."""
    return render_template(
        "about.html",
        title="About - AI Career Intelligence",
    )
