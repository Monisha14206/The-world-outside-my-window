RULES = ("Write in first person using ONLY the facts the user supplied. Never invent events, people, places, "
         "weather, conversations or feelings. If something is missing, omit it. Reply with JSON only.")
def build(task, d):
    ctx = (f"Date: {d.get('date','')}\nPlaces: {d.get('places','')}\nActivity: {d.get('activity','')}\n"
           f"With: {d.get('people','')}\nFeelings chosen: {', '.join(d.get('emotions',[]))}\n"
           f"Reflection: {d.get('reflection','')}\nPhoto captions: {d.get('captions',[])}\nNotes:\n{d.get('notes','')}")
    shapes = {
     "journal": '{"title":str,"story":str,"captions":[str per photo, same count as captions given],"feelings":str,"details":[str]}',
     "title": '{"title":str}',
     "captions": '{"captions":[str, one short cautious caption per photo, same count as captions given]}'}
    extra = {"journal": "Write a warm 2-4 paragraph story. 'feelings' only restates the chosen feelings. 'details' are small things taken from the notes.",
             "title": "Suggest one short evocative title.", "captions": "Use the user's captions/notes; do not describe image content you cannot see."}[task]
    return f"{RULES}\n{extra}\nJSON shape: {shapes[task]}\n\n{ctx}"
