import os
import uuid
import xml.etree.ElementTree as ET
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'your-secret-key'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        archive_file = request.files.get('archive')
        result_files = request.files.getlist('results')
        output_format = request.form.get('format')

        if not archive_file or not result_files:
            flash("Please upload both the archive XML file and result XML files.")
            return redirect(url_for('index'))

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_FOLDER, session_id)
        os.makedirs(session_folder, exist_ok=True)

        # Save archive file
        archive_path = os.path.join(session_folder, archive_file.filename)
        archive_file.save(archive_path)

        # Save result files
        result_filenames = []
        for file in result_files:
            save_path = os.path.join(session_folder, file.filename)
            file.save(save_path)
            result_filenames.append(file.filename)

        try:
            df = extract_data(archive_path, session_folder, result_filenames)
            output_path = os.path.join(session_folder, f"output.{output_format}")
            if output_format == "csv":
                df.to_csv(output_path, index=False)
            else:
                df.to_excel(output_path, index=False)
            return send_file(output_path, as_attachment=True)
        except Exception as e:
            flash(f"Processing failed: {e}")
            return redirect(url_for('index'))

    return render_template('index.html')

def extract_data(archive_file, results_folder, available_files):
    tree = ET.parse(archive_file)
    root = tree.getroot()
    result_files = [res.attrib['file'] for res in root.find('results')]

    records = []
    for filename in result_files:
        if filename not in available_files:
            continue  # Skip missing files

        filepath = os.path.join(results_folder, filename)
        try:
            tree = ET.parse(filepath)
            sample_root = tree.getroot()

            record = {
                'File': filename,
                'SampleID': '',
                'AnalysisDate': ''
            }

            sample_id = sample_root.find(".//st[@n='FIELD_SID_SAMPLE_ID']")
            analysis_date = sample_root.find(".//dt[@n='ANALYSIS_DATE']")
            if sample_id is not None and sample_id.text:
                record['SampleID'] = sample_id.text.strip()
            if analysis_date is not None and analysis_date.text:
                record['AnalysisDate'] = analysis_date.text.strip()

            for param_node in sample_root.findall(".//o[@t='SampleParameterResult']"):
                param_id_el = param_node.find("st[@n='Id']")
                value_el = param_node.find("d[@n='Value']")
                if param_id_el is not None and value_el is not None:
                    param_id = param_id_el.text.strip()
                    value = value_el.text.strip()
                    record[param_id] = value

            records.append(record)

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    return pd.DataFrame(records)

if __name__ == '__main__':
    app.run(debug=True)
