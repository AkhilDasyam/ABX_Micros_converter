from flask import Flask, request, send_file, render_template, flash, redirect, url_for
import pandas as pd
import tempfile
import os
import tarfile  # <- Add this line
import xml.etree.ElementTree as ET  # If you process XML files
from datetime import datetime  # If you use timestamps for filenames

app = Flask(__name__) 

app.secret_key = 'your_secret_key'
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        tar_file = request.files.get("tar_file")
        output_format = request.form.get("output_format")

        if not tar_file or output_format not in ["csv", "xlsx"]:
            flash("Please upload a .tar file and select an output format.")
            return redirect(url_for("index"))

        with tempfile.TemporaryDirectory() as temp_dir:
            tar_path = os.path.join(temp_dir, "archive.tar")
            tar_file.save(tar_path)

            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)

            try:
                with tarfile.open(tar_path) as tar:
                    tar.extractall(path=extract_dir)

                archive_file = next(
                    (f for f in os.listdir(extract_dir) if f.startswith('ar-') and f.endswith('.xml')),
                    None
                )
                if not archive_file:
                    flash("No archive XML file starting with 'ar-' found.")
                    return redirect(url_for("index"))

                archive_path = os.path.join(extract_dir, archive_file)
                tree = ET.parse(archive_path)
                root = tree.getroot()
                result_files = [res.attrib['file'] for res in root.find('results')]

                records = []
                for filename in result_files:
                    if not filename.endswith('.xml'):
                        continue

                    filepath = os.path.join(extract_dir, filename)
                    if not os.path.exists(filepath):
                        continue

                    sample_tree = ET.parse(filepath)
                    sample_root = sample_tree.getroot()

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

                if not records:
                    flash("No valid data records found in the archive.")
                    return redirect(url_for("index"))

                df = pd.DataFrame(records)

                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                output_filename = f"extracted_data_{timestamp}.{output_format}"
                output_path = os.path.join(os.getcwd(), output_filename)

                if output_format == "csv":
                    df.to_csv(output_path, index=False)
                else:
                    df.to_excel(output_path, index=False, engine='openpyxl')

                # Send file as attachment (download) with appropriate headers
                return send_file(
    output_path,
    as_attachment=True,
    download_name=output_filename
)


            except Exception as e:
                flash(f"An unexpected error occurred: {e}")
                return redirect(url_for("index"))

    return render_template("index.html")


@app.route("/success")
def success():
    file_path = request.args.get('file_path')
    return render_template("success.html", file_path=file_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

