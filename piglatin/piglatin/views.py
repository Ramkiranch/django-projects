from django.http import HttpResponse
from django.shortcuts import render

def home(request):
    return render(request,'home.html')

def translate(request):

    original = request.GET['originaltext'].lower()

    translation = ''
    for word in original.split():
        if word[0] in ['a','e','i','o','u']:
            translation += word
            translation += 'yay '
        else:
            translation += word[1:]
            translation += word[0]
            translation += 'ay '
    return render(request, 'translate.html', {'original':original, 'translate':translation})

def about(request):
    return render(request,'about.html')
