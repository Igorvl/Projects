import React, {useState} from "react";
import s from "../../css/Advantage.module.css";

export default () => {
	
	// let [adv, setAdv] = useState([
	// 		{id: 0, num: 45, txt: 'Увеличение скорости загрузки сайта'},
	// 		{id: 1, num: 50, txt: 'Рост продаж с сайта'},
	// 		{id: 2, num: 75, txt: 'Улучшение имиджа компании'},
	// 		{id: 3, num: 36, txt: 'Экономия на привлечении клиента'},
	// 	]
	// );
	
	return (
		<div className={s.global_wrapper}>
			<h2 className={s.adv_H2}>
				Ваши лучшие результаты в бизнесе!
			</h2>
			<h3 className={s.adv_H3}>
				Доверьте создание сайта RMS, и вы заметите разницу:
			</h3>
			<div className={s.adv_wrapper}>
				<div className={s.content_block__item}>
					<div>
						<div className={s.item_num}>45<span className={s.item_num__perc}>%</span></div>
						<span className={s.item_txt}>Увеличение скорости загрузки сайта</span>
					</div>
				</div>
				<div className={s.item_sep}> </div>
				<div className={s.content_block__item}>
					<div>
						<div className={s.item_num}>50<span className={s.item_num__perc}>%</span></div>
						<span className={s.item_txt}>Рост продаж <br/>с сайта</span>
					</div>
				</div>
				<div className={s.item_sep}> </div>
				<div className={s.content_block__item}>
					<div>
						<div className={s.item_num}>75<span className={s.item_num__perc}>%</span></div>
						<span className={s.item_txt}>Улучшение имиджа компании</span>
					</div>
				</div>
				<div className={s.item_sep}> </div>
				<div className={s.content_block__item}>
					<div>
						<div className={s.item_num}>36<span className={s.item_num__perc}>%</span></div>
						<span className={s.item_txt}>Экономия на привлечении клиента</span>
					</div>
				</div>
			</div>
			
			<div className={s.adv_remark}>
				Отчет на основе опроса клиентов RMS
			</div>
		</div>
	
	
	)
}