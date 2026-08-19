from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class LoginForm(AuthenticationForm):
    """Форма входа — переопределяем виджеты под свою вёрстку и русские подписи."""

    username = forms.CharField(
        label="Email или логин",
        widget=forms.TextInput(attrs={
            "class": "auth-field__input",
            "placeholder": "you@mail.ru",
            "autocomplete": "username",
        }),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={
            "class": "auth-field__input",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        }),
    )

    error_messages = {
        "invalid_login": "Неверный email/логин или пароль. Проверьте данные и попробуйте снова.",
        "inactive": "Этот аккаунт отключён.",
    }


class RegisterForm(UserCreationForm):
    """Форма регистрации: логин + email + пароль с подтверждением."""

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "class": "auth-field__input",
            "placeholder": "you@mail.ru",
            "autocomplete": "email",
        }),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Имя пользователя"
        self.fields["username"].widget.attrs.update({
            "class": "auth-field__input",
            "placeholder": "Ваше имя",
            "autocomplete": "username",
        })
        self.fields["password1"].label = "Пароль"
        self.fields["password1"].widget.attrs.update({
            "class": "auth-field__input",
            "placeholder": "Минимум 8 символов",
            "autocomplete": "new-password",
        })
        self.fields["password2"].label = "Повторите пароль"
        self.fields["password2"].widget.attrs.update({
            "class": "auth-field__input",
            "placeholder": "Повторите пароль",
            "autocomplete": "new-password",
        })

    def email_exists(self):
        return User.objects.filter(email__iexact=self.cleaned_data.get("email", "")).exists()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
