import React, {useState} from "react";
import s from "../../css/Advantage.module.css";

export default () => {
	
	let [adv, setAdv] = useState([
			{id: 0, num: 45, txt: 'Увеличение скорости загрузки сайта', key: 0},
			{id: 1, num: 50, txt: 'Рост продаж с сайта', key: 1},
			{id: 2, num: 75, txt: 'Улучшение имиджа компании', key: 2},
			{id: 3, num: 36, txt: 'Экономия на привлечении клиента', key: 3},
		]
	);
	
	setTimeout(() => {
		setAdv = () => {
			adv += 1;
		}
	})
	;
	
	return (
		<div className={s.global_wrapper}>
			<h2 className={s.adv_H2}>
				Ваши лучшие результаты в бизнесе
			</h2>
			<h3 className={s.adv_H3}>
				Доверьте создание сайта RMS, и вы заметите разницу:
			</h3>
			<div className={s.content_block}>
				{adv.map((adv) => {
					return (<div key={adv.key} className={s.content_block__item}>
						<span className={s.item_num} >{adv.num}<span className={s.item_num__perc}>%</span></span>
						<span className={s.item_txt}>{adv.txt}</span>
					</div>)
				})}
			</div>
			
			<span className={s.adv_remark}>
				Отчет на основе опроса клиентов RMS
			</span>
		
		</div>
	)
}