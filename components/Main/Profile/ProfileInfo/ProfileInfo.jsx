import React from 'react';
import s from '../../../../css/ProfileInfo.module.css';
import ava from '../../../../Images/logo.svg';
import Preloader from "../../../Common/Preloader";


export default (props) => {
	return (
		<div className={s.infoContainer}>
			{!props.preloaderOn ?
				<div>
					{!props.choosedUser.photos.large ?
						<img src={ava} className={s.avaPhoto} alt=""/> :
						<div><img src={props.choosedUser.photos.large} className={s.avaPhoto} alt=""/></div>
					}
					<div className={s.title}>
						<div>{props.choosedUser.name}</div>
						<div>{props.choosedUser.status}</div>
					</div>
				</div>
				: <Preloader/>}
		</div>
	)
};
