from django.db import migrations


def remove_focus_ring(apps, schema_editor):
    ChatTheme = apps.get_model('chats', 'ChatTheme')
    for theme in ChatTheme.objects.all():
        if 'focus:ring' in theme.input_field or 'focus:border' in theme.input_field:
            classes = theme.input_field.split()
            classes = [c for c in classes if not c.startswith('focus:')]
            theme.input_field = ' '.join(classes)
            theme.save()


def restore_focus_ring(apps, schema_editor):
    ChatTheme = apps.get_model('chats', 'ChatTheme')
    for theme in ChatTheme.objects.all():
        if 'focus:ring' not in theme.input_field:
            theme.input_field += ' focus:ring-2 focus:ring-emerald-500 focus:border-transparent'
            theme.save()


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0070_fix_theme_field_values'),
    ]

    operations = [
        migrations.RunPython(remove_focus_ring, restore_focus_ring),
    ]
