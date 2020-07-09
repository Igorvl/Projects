import React, {useState, useEffect} from 'react';
import {follow, getUsers, unfollow, totalPages, selectedPage, choosedUserId} from "../../Redux/usersReducer";
import {connect} from "react-redux";
import UsersH from "./UsersH";
import {getApiUsers} from "../../../API/getApiUsers";

const UsersContainer = (props) => {
	
	let [preloaderOn, setPreloaderOn] = useState(false);
	let {getUsers, usersOnPage, choosedPage} = props;
	// хук для запроса на серв. списка пользователей. Производится запись пришедшего списка через CB
	useEffect(() => {
		setPreloaderOn(true);
		getApiUsers(usersOnPage, choosedPage).then(response => {
			getUsers(response.data);
			setPreloaderOn(false);
		})
	}, [getUsers, usersOnPage, choosedPage]);
	
	let paginationNums = [];
	for (let i = 1; i <= props.countPages; i++) {
		paginationNums.push(i);
	}
	
	return <UsersH
		paginationNums={paginationNums}
		usersData={props.usersData}
		choosedPage={props.choosedPage}
		selectedPage={props.selectedPage}
		unfollow={props.unfollow}
		follow={props.follow}
		preloaderOn={preloaderOn}
		choosedUserId={props.choosedUserId}
	/>;
};

const mapStateToProps = (state) => {
	return ({
		usersData: state.usersPage.usersData,
		countPages: state.usersPage.countPages,
		currentPage: state.usersPage.currentPage,
		choosedPage: state.usersPage.choosedPage,
		usersOnPage: state.usersPage.usersOnPage,
	})
};

export default connect(mapStateToProps, {
	// callBacks for mapDispatchToProps
	follow,	unfollow,	getUsers,	totalPages,	selectedPage, choosedUserId,
})(UsersContainer);

