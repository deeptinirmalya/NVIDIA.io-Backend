from worker.celery import client




def send_wl_mail(subject, body, receiver_email, priority: int = 5):
    client.send_task(
        "send_email",
        args=[subject, body, receiver_email],
        kwargs={},
        priority=priority,
        queue="priority_celery"
    )
    print("✅ Task sent to CloudAMQP")

