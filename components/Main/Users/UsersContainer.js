import React, {useEffect} from 'react';
import {followAC, getUsersAC, unfollowAC, totalPagesAC, choosedPageAC} from "../../Redux/usersReducer";
import {connect} from "react-redux";
import UsersH from "./UsersH";
import {useState} from "react";
import * as axios from "axios";

const UsersContainer = (props) => {
	
	let [preloaderOn, setPreloaderOn] = useState(false);
	
	// хук для запроса на серв. Производится запись пришедшего списка через CB
	useEffect(() => {
		setPreloaderOn(true);
		axios.get(`https://social-network.samuraijs.com/api/1.0/users?count=${props.usersOnPage}&page=${props.choosedPage}`).then(response => {
			props.getUsersCB(response.data);
			setPreloaderOn(false);
		})
	}, [props.choosedPage]);
	
	let paginationNums = [];
	for (let i = 1; i <= props.totalPages; i++) {
		paginationNums.push(i);
	}
	
	return <UsersH
		paginationNums={paginationNums}
		usersData={props.usersData}
		choosedPageCB={props.choosedPageCB}
		choosedPage={props.choosedPage}
		unfollowCB={props.unfollowCB}
		followCB={props.followCB}
		preloaderOn={preloaderOn}
	/>;
};

const mapStateToProps = (state) => {
	return ({
		usersData: state.usersPage.usersData,
		totalPages: state.usersPage.totalPages,
		currentPage: state.usersPage.currentPage,
		choosedPage: state.usersPage.choosedPage,
		usersOnPage: state.usersPage.usersOnPage,
	})
};
const mapDispatchToProps = (dispatch) => {
	return (
		{
			// callbacks for buttons from Users
			followCB: userId => dispatch(followAC(userId)),
			unfollowCB: userId => dispatch(unfollowAC(userId)),
			getUsersCB: usersData => dispatch(getUsersAC(usersData)),
			totalPagesCB: totalPages => dispatch(totalPagesAC(totalPages)),
			choosedPageCB: choosedPage => dispatch(choosedPageAC(choosedPage)),
		}
	)
};
export default connect(mapStateToProps, mapDispatchToProps)(UsersContainer);
// export default connect(mapStateToProps, mapDispatchToProps)(UsersC);

