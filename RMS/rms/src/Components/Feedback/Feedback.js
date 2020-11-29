import React from "react";
import s from '../../css/feedback.module.css';
import Commas from '../../img/commas.svg'

const Feedback = () => {
	return (
		<div className={s.grid}>
			<div className={s.img}>
			{/*<Commas/>*/}
			</div>
			<div className={s.info_box}>
				<h2>RMS делает сайты которые гарантированно работают и приносят доход</h2>

				
				<span className={s.info_box_txt}>Команда RMS делает эффективные сайты. Сначала я скачала их руководство, которое помогло улучшить продажи и исправить ошибки, но потом захотелось большего и я заказала дизайн сайта. Результаты меня очень обрадовали! Продажи выросли более чем в 2 раза.</span>
				<div>
					<span>Екатерина Субботина</span>
					<span>Индивидуальный предприниматель</span>
					
					
					<script src="https://fb.me/react-with-addons-15.1.0.js"></script>
					<script src="https://fb.me/react-dom-15.1.0.js"></script>

					<script src="https://code.jquery.com/jquery-3.1.0.js"></script>
					<div id="results"></div>
					
					<script >
						var resultsDiv = $('#results');
						
						var params = JSON.stringify({
						"cmd": "getAuthSms",
						"params": {
						"tel": "+79037957098",
					}
					});
						params = {
						q: params
					};
						
						function authSmsCmd(params,callback){
						
						$.ajax({
							url: 'https://tradernet.ru/api',
							method: 'POST',
							data: params,
							dataType: 'json',
							success: callback,
							error: function (err) {
								console.log('Error: ' + err.errMsg);
							}
						});
						
					}
						
						authSmsCmd(params,function(json){
						
						var result=prompt("Вводите код смс");
						
						if(result) {
						$.ajax({
						url: 'https://tradernet.ru/api/check-login-password',
						method: 'POST',
						data: {
						rememberMe: 1,
						auth_code_id: json.auth_code_id,
						sms: result,
						mode: 'sms'
					},
						success: function (responseText) {
						resultsDiv.text(responseText);
					},
						error: function (err) {
						
						
						resultsDiv.text('Error: ' + err.statusText);
					}
					});
					}
					
					});
					</script>
					
					
				</div>
			</div>
		</div>
	)
};

export default Feedback