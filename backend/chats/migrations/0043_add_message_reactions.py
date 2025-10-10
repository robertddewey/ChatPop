# Generated manually for emoji reactions feature

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chats', '0042_add_reply_preview_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageReaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('emoji', models.CharField(help_text='Emoji character', max_length=10)),
                ('fingerprint', models.CharField(blank=True, db_index=True, help_text='Anonymous user fingerprint', max_length=255, null=True)),
                ('username', models.CharField(help_text='Username at time of reaction', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='chats.message')),
                ('user', models.ForeignKey(blank=True, help_text='Logged-in user who reacted', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='message_reactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['message', 'emoji'], name='chats_messa_message_idx'),
        ),
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['message', 'user'], name='chats_messa_message_user_idx'),
        ),
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['message', 'fingerprint'], name='chats_messa_message_finger_idx'),
        ),
        migrations.AddConstraint(
            model_name='messagereaction',
            constraint=models.UniqueConstraint(condition=models.Q(('user__isnull', False)), fields=('message', 'user'), name='unique_message_user_reaction'),
        ),
        migrations.AddConstraint(
            model_name='messagereaction',
            constraint=models.UniqueConstraint(condition=models.Q(('user__isnull', True)), fields=('message', 'fingerprint'), name='unique_message_fingerprint_reaction'),
        ),
    ]
