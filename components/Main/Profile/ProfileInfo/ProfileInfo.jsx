import React, {useState} from 'react';
import s from '../../../../css/ProfileInfo.module.css';
import ava from '../../../../Images/logo.svg';
import Preloader from "../../../Common/Preloader";


export default (props) => {
	let [statusState, setStatusState] = useState(false);
	const clickOnStatus = () => {
		setStatusState(true);
	};
	return (
		<div>
			{!props.preloaderOn ?
				<div  className={s.infoContainer}>
					{!props.choosedUser.photos.large ?
						<img src={ava} className={s.avaPhoto} alt=""/> :
						<div><img src={props.choosedUser.photos.large} className={s.avaPhoto} alt=""/></div>
					}
					<div className={s.title}>
						<div>{props.choosedUser.name ? props.choosedUser.name : props.choosedUser.fullName}</div>
						<div>{props.choosedUser.status }</div>
						{!statusState ?
							<div onDoubleClick={clickOnStatus}>{props.choosedUser.status}</div>	:
							<div className={s.titleInput}>
								<input type="text"
				            defaultValue={props.choosedUser.status}
				            onBlur={()=>{setStatusState(false)}}
				            className={s.statusInput}
				            autoFocus={true}/>
							</div>
						}
						
					</div>
				</div>
				: <Preloader/>}
		</div>
	)
};
