import React from "react";
import s from "../../css/Advantage.module.css";

export default (props) => {
	return (
		<div className={s.global_wrapper}>
			<h2 className={s.adv_H2}>
				Ваши лучшие результаты в бизнесе
			</h2>
			<h3 className={s.adv_H3}>
				Доверьте создание сайта RMS, и вы заметите разницу:
			</h3>
			
			<span className={s.adv_remark}>
				Отчет на основе опроса клиентов RMS
			</span>
		
		</div>
	)
}