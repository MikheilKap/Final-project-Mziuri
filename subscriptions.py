from flask import Blueprint, jsonify
from models.subscription import Subscription

subscriptions = Blueprint('subscriptions', __name__)

@subscriptions.route('/subscriptions/<int:user_id>')
def get_subscriptions(user_id):

    all_subs = Subscription.query.filter_by(
        user_id=user_id
    ).all()

    result = []

    for sub in all_subs:

        result.append({
            "service_name": sub.service_name,
            "monthly_cost": sub.monthly_cost,
            "renewal_date": sub.renewal_date
        })

    return jsonify(result)