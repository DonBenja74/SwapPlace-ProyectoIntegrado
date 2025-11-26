from django.db import models
from django.contrib.auth.models import User

class Producto(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class Trueque(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
    ]
    solicitante = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trueques_solicitados')
    receptor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trueques_recibidos')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.solicitante.username} → {self.receptor.username} ({self.estado})"


class Chat(models.Model):
    trueque = models.OneToOneField(Trueque, on_delete=models.CASCADE, related_name='chat')
    usuarios = models.ManyToManyField(User)
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        try:
            nombres = ', '.join([u.username for u in self.usuarios.all()])
        except:
            nombres = "Chat"
        return f"Chat entre {nombres}"


class Mensaje(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='mensajes')
    autor = models.ForeignKey(User, on_delete=models.CASCADE)
    contenido = models.TextField(max_length=500)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.autor.username}: {self.contenido[:30]}"


class Notificacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones')
    titulo = models.CharField(max_length=150)
    mensaje = models.CharField(max_length=300)
    tipo = models.CharField(max_length=50, blank=True)
    link = models.CharField(max_length=300, blank=True)  # ruta relativa p.ej. '/chat/5/'
    creado = models.DateTimeField(auto_now_add=True)
    visible = models.BooleanField(default=True)

    def __str__(self):
        return f"Notif a {self.usuario.username}: {self.titulo}"
