"""Gmail channel adapter: a review inbox checked over IMAP, replies sent over SMTP.

People forward (or write) a draft to the review address; ENGANO replies in the
same thread with the decision, cited findings and a suggested rewrite.
No webhook or Google Cloud project is needed, only a Gmail app password.
"""
