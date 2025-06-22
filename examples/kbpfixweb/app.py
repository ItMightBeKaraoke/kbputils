import flask
import io
import kbputils
import tempfile
import os

app = flask.Flask(__name__)

if not os.path.exists('.secret'):
    import secrets
    with open('.secret', 'w') as f:
        f.write(secrets.token_hex())

with open(".secret", "rb") as f:
    app.secret_key = f.read()

landing_page = """
<!doctype html>
<head><title>KBP fix tool</title></head>
<body>
<h1>KBP Fixer</h1>
<p>Upload a kbp file to fix</p>
<form action="/process" method="post" enctype="multipart/form-data">
<input type="file" accept=".kbp" name="file" />
<input type="submit" value="Upload" />
</form>
</body>
"""

kbpcheck_result = """
<!doctype html>
<head><title>KBP fix tool</title></head>
<body>
<h1>KBP Fixer</h1>

{% if syntax_errors or logic_errors %}
<form action="/fix" method="post">
{% endif %}

{% if syntax_errors %}
<h2>Syntax Errors</h2>
{% for x in syntax_errors %}
<fieldset>
<legend>{{x}}</legend>
    <div>
    <input type="radio" name="syntax{{loop.index0}}" value="automatic" id="syntax_sln{{loop.index0}}" checked/><label for="syntax_sln{{loop.index0}}">Accept automatic fix</label>
    </div>
</fieldset>
{% endfor %}
{% endif %}

{% if logic_errors %}
<h2>Logic Errors</h2>
{% for name, solutions in logic_errors %}
{% set err_index = loop.index0 %}
<fieldset>
<legend>{{name}}</legend>
{% for s in solutions %}
    <div>
    <input type="radio" name="error{{err_index}}" value="{{s}}" id="{{s}}"/><label for="{{s}}">{{solutions[s].description}}</label>
    {% for param in solutions[s].params %}
        <select name="{{s}}_param_{{param}}" id="{{s}}_param_{{param}}">
                <option value="">-- Choose {{param}} --</option>
            {% for choice_id, desc in solutions[s].params[param] %}
                <option value="{{choice_id}}">{{choice_id}} - {{desc}}</option>
            {% endfor %}
        </select>
    {% endfor %}
    </div>
{% endfor %}
    <div>
    <input type="radio" name="error{{err_index}}" value="nochange" id="nochange{{err_index}}" checked/><label for="nochange{{err_index}}">Leave as is</label>
    </div>
</fieldset>
{% endfor %}
{% endif %}

{% if syntax_errors or logic_errors %}
<div>
<input type="submit" value="Run fixes" />
</div>
</form>
<form action="/delete" method="post">
<p>If you are done trying fixes on this file, you can click below, otherwise it will be cleaned up within the next 24 hours.</p>
<input type="submit" value="Delete file" />
</form>
{% else %}
<p>No errors detected. Have a nice day!</p>
<p><a href="/">Process more files</p>
{% endif %}
</body>
"""

@app.get('/')
def hello():
    return landing_page

@app.post('/process')
def process():
    if 'kbpfile' in flask.session:
       tmp = flask.session.pop('kbpfile')
       if os.path.exists(tmp):
           os.remove(tmp)
    flask.session.clear()
    # NamedTemporaryFile could be a bit easier, but delete_on_close option wasn't added until 3.12
    fd, fname = tempfile.mkstemp(dir="tmp")
    # FileStorage.save requires a binary handle or filename. Apparently despite mkstemp supposedly
    # defaulting to binary, wrapping in fdopen sends it back to text unless otherwise specified
    fp = os.fdopen(fd, mode='wb')
    flask.session['kbpfile'] = fname
    flask.session['kbpfilename'] = flask.request.files['file'].filename
    flask.request.files['file'].save(fp)
    fp.close()
    kbp = kbputils.kbp.KBPFile(fname, tolerant_parsing=True, resolve_wipe=False)
    syntax_errors = kbp.onload_modifications
    logic_errors = []
    sln_no = 0
    for err in kbp.logicallyValidate():
        solutions = {}
        logic_errors.append((str(err), solutions))
        for s in err.propose_solutions(kbp):
            solution_name = f'sln{sln_no}'
            flask.session[solution_name] = s.compact()
            solutions[solution_name] = {"description": s.params['description'], "params": s.free_params or {}}
            sln_no += 1

    if not (syntax_errors or logic_errors):
        os.remove(fname)
    return flask.render_template_string(kbpcheck_result, syntax_errors=syntax_errors, logic_errors=logic_errors, kbp=kbp)

@app.post('/fix')
def fix():
    kbp = kbputils.kbp.KBPFile(flask.session['kbpfile'], tolerant_parsing=True, resolve_wipe=False)
    for x in flask.request.form:
        choice = flask.request.form[x]
        if choice.startswith("sln") and choice in flask.session:
            action = kbputils.kbp.KBPAction.expand(flask.session[choice])
            for param in filter(lambda key: key.startswith(choice + "_param_"), flask.request.form):
                name = param.split("_")[2]
                if name not in action.params:
                    action.params[name] = int(flask.request.form[param])
            action.run(kbp)

    # Yes, this is ugly. While flask.send_file exists, the file seems to be closed prematurely when using that
    # Creating an actual temporary file would be a pain too because it would have to be cleaned up
    # And kbpfile wants a text handle, but sending text to flask will use \n, so it needs to be bytes
    out = io.BytesIO()
    wrapped = io.TextIOWrapper(out, encoding='utf-8', newline='\r\n')
    kbp.writeFile(wrapped)
    #return flask.send_file(out, as_attachment=True, download_name=flask.session['kbpfilename'])
    newname = "_kbpfix".join(os.path.splitext(flask.session['kbpfilename']))
    return flask.make_response((out.getvalue(), 200, {
        "Content-Disposition": f"attachment; filename={newname}",
        "Content-Type": "text/plain"
    }))

@app.post('/delete')
def delete():
    if flask.session['kbpfile']:
       tmp = flask.session.pop('kbpfile')
       if os.path.exists(tmp):
           os.remove(tmp)
    flask.session.clear()
    return flask.redirect('/')
