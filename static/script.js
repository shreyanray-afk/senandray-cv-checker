document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('cvForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const btnText = document.querySelector('.btn-text');
    const spinner = document.getElementById('loadingSpinner');
    const inputSection = document.querySelector('.input-section');
    const resultSection = document.getElementById('resultSection');
    const resultContent = document.getElementById('resultContent');
    const resetBtn = document.getElementById('resetBtn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const cvText = document.getElementById('cvText').value.trim();
        const jobDesc = document.getElementById('jobDesc').value.trim();

        if (!cvText) return;

        // Set Loading State
        analyzeBtn.disabled = true;
        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');

        try {
            const response = await fetch('http://localhost:5000/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ cv_text: cvText, job_desc: jobDesc })
            });

            const data = await response.json();

            if (response.ok) {
                // Parse markdown to HTML
                resultContent.innerHTML = marked.parse(data.result);
                
                // UI Transitions
                inputSection.classList.add('hidden');
                resultSection.classList.remove('hidden');
                resultSection.scrollIntoView({ behavior: 'smooth' });
            } else {
                throw new Error(data.error || 'Failed to analyze CV');
            }
        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            // Reset Loading State
            analyzeBtn.disabled = false;
            btnText.classList.remove('hidden');
            spinner.classList.add('hidden');
        }
    });

    resetBtn.addEventListener('click', () => {
        resultSection.classList.add('hidden');
        inputSection.classList.remove('hidden');
        document.getElementById('cvText').value = '';
        document.getElementById('jobDesc').value = '';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
});
