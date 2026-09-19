from app.services.template_service import TemplateService

def test_template_variable_extraction():
    content = "Hello {{name}}, your plan {{plan}} in {{city}} is active for {{name}}."
    vars = TemplateService.extract_variables(content)
    assert vars == ["name", "plan", "city"]

def test_template_rendering():
    content = "Hi {{name}}, your order for {{item}} is confirmed. We will reach you at {{phone}}."
    contact = {
        "name": "Siddharth",
        "phone": "919876543210",
        "email": "sid@example.com",
        "custom_fields": {"item": "Premium AI Bot"}
    }
    rendered = TemplateService.render_template(content, contact)
    assert rendered == "Hi Siddharth, your order for Premium AI Bot is confirmed. We will reach you at 919876543210."
