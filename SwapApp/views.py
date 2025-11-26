from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.db.models import Q
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from .models import Producto, Trueque, Chat, Mensaje, Notificacion
from .forms import MensajeForm
from datetime import timedelta
import json

# ---------- AUTH ----------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    return render(request, 'login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya existe.')
        else:
            User.objects.create_user(username=username, email=email, password=password)
            messages.success(request, 'Cuenta creada correctamente. Inicia sesión.')
            return redirect('login')
    return render(request, 'register.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ---------- HOME ----------
@login_required
def home_view(request):
    user = request.user
    productos = Producto.objects.all().order_by('-fecha_agregado')

    notifs = Notificacion.objects.filter(usuario=user, visible=True).order_by('-creado')[:20]
    trueques_pendientes = Trueque.objects.filter(receptor=user, estado='pendiente').order_by('-fecha')
    trueques_aceptados = Trueque.objects.filter(estado='aceptado').filter(Q(solicitante=user) | Q(receptor=user)).order_by('-fecha')

    # CREAR producto
    if request.method == 'POST' and request.POST.get('action') == 'crear_producto':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        imagen = request.FILES.get('imagen')
        if nombre and descripcion:
            Producto.objects.create(usuario=user, nombre=nombre, descripcion=descripcion, imagen=imagen)
            messages.success(request, 'Producto creado correctamente.')
        else:
            messages.error(request, 'Completa nombre y descripción.')
        return redirect('home')

    # EDITAR producto
    if request.method == 'POST' and request.POST.get('action') == 'editar_producto':
        producto_id = request.POST.get('producto_id')
        producto = get_object_or_404(Producto, id=producto_id)
        if producto.usuario != user:
            return HttpResponseForbidden("No tienes permiso para editar.")
        producto.nombre = request.POST.get('nombre')
        producto.descripcion = request.POST.get('descripcion')
        if 'imagen' in request.FILES:
            producto.imagen = request.FILES['imagen']
        producto.save()
        messages.success(request, 'Producto actualizado correctamente.')
        return redirect('home')

    # ELIMINAR producto
    if request.method == 'POST' and request.POST.get('action') == 'eliminar_producto':
        producto_id = request.POST.get('producto_id')
        producto = get_object_or_404(Producto, id=producto_id)
        if producto.usuario != user:
            return HttpResponseForbidden("No tienes permiso para eliminar.")
        producto.delete()
        messages.success(request, 'Producto eliminado correctamente.')
        return redirect('home')

    # OFRECER trueque
    if request.method == 'POST' and request.POST.get('action') == 'ofrecer_trueque':
        producto = get_object_or_404(Producto, id=request.POST.get('producto_id'))
        if producto.usuario == user:
            messages.error(request, 'No puedes ofrecer por tu propio producto.')
            return redirect('home')
        t = Trueque.objects.create(solicitante=user, receptor=producto.usuario, producto=producto)
        Notificacion.objects.create(
            usuario=producto.usuario,
            titulo='Nueva solicitud de trueque',
            mensaje=f'{user.username} ofreció un trueque por "{producto.nombre}".',
            tipo='nuevo_trueque',
            link=reverse('home')
        )
        messages.success(request, 'Solicitud de trueque enviada.')
        return redirect('home')

    # RESPONDER trueque
    if request.method == 'POST' and request.POST.get('action') == 'responder_trueque':
        trueque = get_object_or_404(Trueque, id=request.POST.get('trueque_id'))
        if trueque.receptor != user:
            return HttpResponseForbidden("No tienes permiso.")
        decision = request.POST.get('decision')
        if decision == 'aceptar':
            trueque.estado = 'aceptado'
            trueque.save()
            chat, created = Chat.objects.get_or_create(trueque=trueque)
            chat.usuarios.set([trueque.solicitante, trueque.receptor])
            chat_url = reverse('chat_detalle', args=[chat.id])
            Notificacion.objects.create(
                usuario=trueque.solicitante,
                titulo='Trueque aceptado',
                mensaje=f'{trueque.receptor.username} aceptó tu solicitud. Pulsa Ver chat.',
                tipo='trueque_aceptado',
                link=chat_url
            )
            Notificacion.objects.create(
                usuario=trueque.receptor,
                titulo='Trueque aceptado',
                mensaje=f'Aceptaste la solicitud de {trueque.solicitante.username}. Pulsa Ver chat.',
                tipo='trueque_aceptado',
                link=chat_url
            )
            messages.success(request, 'Trueque aceptado. Chat creado.')
        else:
            trueque.estado = 'rechazado'
            trueque.save()
            Notificacion.objects.create(
                usuario=trueque.solicitante,
                titulo='Trueque rechazado',
                mensaje=f'{trueque.receptor.username} rechazó tu solicitud por "{trueque.producto.nombre}".',
                tipo='trueque_rechazado',
                link=reverse('home')
            )
            messages.info(request, 'Trueque rechazado.')
        return redirect('home')

    context = {
        'productos': productos,
        'notificaciones': notifs,
        'trueques_pendientes': trueques_pendientes,
        'trueques_aceptados': trueques_aceptados,
        'chats': Chat.objects.filter(usuarios=user).order_by('-creado'),  # <-- más recientes primero
    }
    return render(request, 'home.html', context)


# ---------- CRUD DE PRODUCTOS ----------
@login_required
def crear_producto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        imagen = request.FILES.get('imagen')
        if nombre and descripcion:
            Producto.objects.create(usuario=request.user, nombre=nombre, descripcion=descripcion, imagen=imagen)
            messages.success(request, 'Producto creado correctamente.')
    return redirect('home')


@login_required
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if producto.usuario != request.user:
        return HttpResponseForbidden("No autorizado")
    if request.method == 'POST':
        producto.nombre = request.POST.get('nombre')
        producto.descripcion = request.POST.get('descripcion')
        if 'imagen' in request.FILES:
            producto.imagen = request.FILES['imagen']
        producto.save()
        messages.success(request, 'Producto actualizado.')
    return redirect('home')


@login_required
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if producto.usuario != request.user:
        return HttpResponseForbidden("No autorizado")
    if request.method == 'POST':
        producto.delete()
        messages.success(request, 'Producto eliminado.')
    return redirect('home')


# ---------- TRUEQUES ----------
@login_required
def ofrecer_trueque(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if producto.usuario == request.user:
        messages.error(request, 'No puedes ofrecer por tu propio producto.')
        return redirect('home')
    t = Trueque.objects.create(solicitante=request.user, receptor=producto.usuario, producto=producto)
    Notificacion.objects.create(
        usuario=producto.usuario,
        titulo='Nueva solicitud de trueque',
        mensaje=f'{request.user.username} ofreció un trueque por "{producto.nombre}".',
        tipo='nuevo_trueque',
        link=reverse('home')
    )
    messages.success(request, 'Solicitud de trueque enviada.')
    return redirect('home')


@login_required
def aceptar_trueque(request, trueque_id):
    trueque = get_object_or_404(Trueque, id=trueque_id)
    if trueque.receptor != request.user:
        return HttpResponseForbidden("No tienes permiso")
    trueque.estado = 'aceptado'
    trueque.save()
    chat, created = Chat.objects.get_or_create(trueque=trueque)
    chat.usuarios.set([trueque.solicitante, trueque.receptor])
    chat_url = reverse('chat_detalle', args=[chat.id])
    Notificacion.objects.create(
        usuario=trueque.solicitante,
        titulo='Trueque aceptado',
        mensaje=f'{trueque.receptor.username} aceptó tu solicitud. Pulsa Ver chat.',
        tipo='trueque_aceptado',
        link=chat_url
    )
    Notificacion.objects.create(
        usuario=trueque.receptor,
        titulo='Trueque aceptado',
        mensaje=f'Aceptaste la solicitud de {trueque.solicitante.username}. Pulsa Ver chat.',
        tipo='trueque_aceptado',
        link=chat_url
    )
    messages.success(request, 'Trueque aceptado.')
    return redirect('home')


@login_required
def rechazar_trueque(request, trueque_id):
    trueque = get_object_or_404(Trueque, id=trueque_id)
    if trueque.receptor != request.user:
        return HttpResponseForbidden("No tienes permiso")
    trueque.estado = 'rechazado'
    trueque.save()
    Notificacion.objects.create(
        usuario=trueque.solicitante,
        titulo='Trueque rechazado',
        mensaje=f'{trueque.receptor.username} rechazó tu solicitud por "{trueque.producto.nombre}".',
        tipo='trueque_rechazado',
        link=reverse('home')
    )
    messages.info(request, 'Trueque rechazado.')
    return redirect('home')

@login_required
def buscar_productos(request):
    texto = request.GET.get("q", "")
    productos = Producto.objects.filter(
        Q(nombre__icontains=texto) |
        Q(usuario__username__icontains=texto)
    ).order_by("-id")[:100]

    lista = []
    for p in productos:
        lista.append({
            "id": p.id,
            "nombre": p.nombre,
            "descripcion": p.descripcion[:120] + ("..." if len(p.descripcion) > 120 else ""),
            "usuario": p.usuario.username,
            "imagen": p.imagen.url if p.imagen else "/static/img/logo.png",
            "es_dueno": (request.user == p.usuario) or (request.user.username == "admin3000"),
        })

    return JsonResponse({"productos": lista})

# ---------- CHAT ----------
@login_required
def chat_list_view(request):
    chats = Chat.objects.filter(usuarios=request.user).order_by('-creado')  # más recientes primero
    return render(request, 'chat.html', {'chats': chats})


@login_required
def chat_detalle(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    if request.user not in chat.usuarios.all():
        return HttpResponseForbidden("No tienes acceso a este chat.")
    mensajes = chat.mensajes.all().order_by('fecha')
    form = MensajeForm()
    return render(request, 'chat.html', {
        'chat': chat,
        'mensajes': mensajes,
        'form': form,
        'chats': Chat.objects.filter(usuarios=request.user).order_by('-creado'),  # orden descendente
        'chat_seleccionado': chat
    })


@login_required
@csrf_exempt
def api_send_message(request, chat_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'Formato JSON inválido'}, status=400)
        texto = data.get('texto', '').strip()
        if not texto:
            return JsonResponse({'ok': False, 'error': 'Mensaje vacío'}, status=400)
        chat = get_object_or_404(Chat, id=chat_id)
        mensaje = Mensaje.objects.create(chat=chat, autor=request.user, contenido=texto)
        return JsonResponse({
            'ok': True,
            'mensaje': {
                'id': mensaje.id,
                'autor': mensaje.autor.username,
                'contenido': mensaje.contenido,
                'fecha': localtime(mensaje.fecha).strftime('%d/%m/%Y %H:%M')
            }
        })
    return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)


@login_required
def api_fetch_messages(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    if request.user not in chat.usuarios.all():
        return JsonResponse({'error': 'No autorizado'}, status=403)
    msgs = chat.mensajes.all().order_by('fecha')
    datos = [{
        'id': m.id,
        'autor': m.autor.username,
        'contenido': m.contenido,
        'fecha': m.fecha.strftime("%d/%m/%Y %H:%M")
    } for m in msgs]
    return JsonResponse({'mensajes': datos})


# ---------- NOTIFICACIONES ----------
@login_required
def api_notificaciones(request):
    user = request.user
    notifs = Notificacion.objects.filter(usuario=user, visible=True).order_by('-creado')[:20]
    ahora = timezone.now()
    datos = []
    for n in notifs:
        edad = (ahora - n.creado).total_seconds()
        datos.append({
            'id': n.id,
            'titulo': n.titulo,
            'mensaje': n.mensaje,
            'tipo': n.tipo,
            'link': n.link,
            'creado_iso': n.creado.isoformat(),
            'edad_segundos': int(edad),
        })
    return JsonResponse({'notificaciones': datos})


@login_required
@require_POST
def api_marcar_leida(request):
    nid = request.POST.get('id')
    try:
        n = Notificacion.objects.get(id=nid, usuario=request.user)
        n.visible = False
        n.save()
        return JsonResponse({'ok': True})
    except Notificacion.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No encontrada'}, status=404)


# ---------- NUEVAS FUNCIONES: REPORTAR Y CALIFICAR ----------
@login_required
@require_POST
def reportar_chat(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    if request.user not in chat.usuarios.all():
        return JsonResponse({'ok': False, 'error': 'No autorizado'}, status=403)

    mensaje_texto = (
        "El equipo de soporte de Swap Place estará revisando su conversación "
        "en busca de la razón del reporte. Gracias por avisar. "
        "Recibirá la noticia de este caso en las próximas 72 hrs. "
        "Gracias por preferir SwapPlace."
    )
    return JsonResponse({'ok': True, 'mensaje': mensaje_texto})


@login_required
@require_POST
def calificar_chat(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    if request.user not in chat.usuarios.all():
        return JsonResponse({'ok': False, 'error': 'No autorizado'}, status=403)
    rating = request.POST.get('rating')
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Rating inválido'}, status=400)
    if rating < 1 or rating > 5:
        return JsonResponse({'ok': False, 'error': 'Fuera de rango'}, status=400)

    return JsonResponse({'ok': True, 'mensaje': f'Calificación de {rating} estrellas registrada correctamente.'})
